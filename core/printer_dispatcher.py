"""
Printer Dispatcher for Printer InkSaver
Dispatches processed PDFs to Canon / Ricoh / Network printers via:
1. LPD (RFC 1179) over Port 515 with student name and job name in control file
2. PJL + Raw Socket over Port 9100
3. IPP (Internet Printing Protocol RFC 8010) over Port 631
4. Native CUPS `lp` command (macOS / Linux)
5. Spool / Mock mode (when offline or for simulation)
"""

import os
import socket
import struct
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path


def check_printer_connectivity(ip: str = "172.16.4.9", timeout: float = 1.2) -> dict:
    """
    Test printer reachability across common printing ports (515, 631, 9100, 80, 8000).
    """
    ports = [515, 631, 9100, 8000, 80]
    results = {}
    is_online = False
    t_start = time.time()

    for port in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            results[str(port)] = True
            is_online = True
        except Exception:
            results[str(port)] = False
        finally:
            s.close()

    latency_ms = round((time.time() - t_start) * 1000, 1)

    return {
        "online": is_online,
        "ip": ip,
        "ports": results,
        "latency_ms": latency_ms,
        "recommended_protocol": "lpd" if results.get("515") else ("ipp" if results.get("631") else "socket")
    }


def build_pjl_payload(
    pdf_bytes: bytes,
    student_name: str,
    job_name: str,
    duplex: bool = True,
    copies: int = 1,
    binding: str = "long",
    collate: bool = True
) -> bytes:
    """
    Wrap PDF in standard PJL (Printer Job Language) header and trailer.
    PJL is recognized by Canon, HP, Ricoh, Brother, Xerox printers.
    Supports binding edge (LONGEDGE vs SHORTEDGE) and collate (ON vs OFF).
    """
    duplex_val = "ON" if duplex else "OFF"
    binding_val = "SHORTEDGE" if (duplex and str(binding).lower() == "short") else "LONGEDGE"
    collate_val = "ON" if collate else "OFF"
    # Allow letters, numbers, spaces, hyphens, underscores, and unicode characters
    clean_student = " ".join((student_name or "Student").split()).strip()
    clean_job = " ".join((job_name or "Document.pdf").split()).strip()

    pjl_header = (
        f"\x1b%-12345X@PJL\r\n"
        f'@PJL SET USERNAME = "{clean_student}"\r\n'
        f'@PJL SET JOBNAME = "{clean_job}"\r\n'
        f"@PJL SET COPIES = {copies}\r\n"
        f"@PJL SET QTY = {copies}\r\n"
        f"@PJL SET DUPLEX = {duplex_val}\r\n"
        f"@PJL SET BINDING = {binding_val}\r\n"
        f"@PJL SET COLLATE = {collate_val}\r\n"
        f"@PJL SET HOLD = ON\r\n"
        f"@PJL SET HOLDTYPE = HOLD\r\n"
        f"@PJL ENTER LANGUAGE = PDF\r\n"
    ).encode("utf-8")

    pjl_footer = b"\r\n\x1b%-12345X@PJL EOJ\r\n\x1b%-12345X"

    return pjl_header + pdf_bytes + pjl_footer


def send_via_lpd(
    pdf_bytes: bytes,
    student_name: str,
    job_name: str,
    duplex: bool = True,
    copies: int = 1,
    ip: str = "172.16.4.9",
    queue: str = "print",
    timeout: float = 10.0,
    binding: str = "long",
    collate: bool = True
) -> dict:
    """
    Send job via Line Printer Daemon (LPD) protocol RFC 1179.
    Places student_name in LPD control file ('P' and 'L' attributes)
    so Canon's Secure Print / Hold queue displays the user on its screen.
    Uses 'l' (binary raw mode) so PDF binary control characters are not escaped.
    """
    clean_user = " ".join((student_name or "Student").split()).strip()
    clean_job = " ".join((job_name or "Document.pdf").split()).strip()
    hostname = "localhost"
    job_id = "001"

    # Wrap in PJL to guarantee duplex, binding, collate, and secure print tags
    payload = build_pjl_payload(pdf_bytes, student_name, job_name, duplex, copies, binding=binding, collate=collate)

    # Build LPD control file content (RFC 1179: 'l' for binary raw print stream)
    cf_lines = [
        f"H{hostname}",
        f"P{clean_user}",
        f"J{clean_job}",
        f"C{clean_user}",
        f"L{clean_user}",
        f"N{clean_job}",
        f"ldfA{job_id}{hostname}",
        f"UdfA{job_id}{hostname}",
    ]
    cf_data = ("\n".join(cf_lines) + "\n").encode("utf-8")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)

    try:
        s.connect((ip, 515))

        # 1. Receive-a-printer-job command: \x02<queue>\n
        s.sendall(f"\x02{queue}\n".encode("ascii"))
        ack = s.recv(1)
        if ack != b"\x00":
            # Retry with empty or direct queue
            s.close()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((ip, 515))
            s.sendall(b"\x02direct\n")
            ack = s.recv(1)
            if ack != b"\x00":
                raise RuntimeError(f"LPD queue rejected by printer: ack={ack!r}")

        # 2. Receive control file command: \x02<count> cfA<id><host>\n
        cf_cmd = f"\x02{len(cf_data)} cfA{job_id}{hostname}\n".encode("ascii")
        s.sendall(cf_cmd)
        ack = s.recv(1)
        if ack != b"\x00":
            raise RuntimeError(f"LPD control file cmd rejected: ack={ack!r}")

        # Send control file bytes + 0x00
        s.sendall(cf_data + b"\x00")
        ack = s.recv(1)
        if ack != b"\x00":
            raise RuntimeError(f"LPD control file data rejected: ack={ack!r}")

        # 3. Receive data file command: \x03<count> dfA<id><host>\n
        df_cmd = f"\x03{len(payload)} dfA{job_id}{hostname}\n".encode("ascii")
        s.sendall(df_cmd)
        ack = s.recv(1)
        if ack != b"\x00":
            raise RuntimeError(f"LPD data file cmd rejected: ack={ack!r}")

        # Send data file bytes + 0x00
        s.sendall(payload + b"\x00")
        ack = s.recv(1)
        if ack != b"\x00":
            raise RuntimeError(f"LPD data transfer rejected: ack={ack!r}")

        return {
            "success": True,
            "protocol": "LPD (RFC 1179)",
            "message": f"Job dispatched to Canon printer hold queue for '{student_name}'.",
            "bytes_sent": len(payload)
        }
    finally:
        s.close()


def send_via_raw_socket(
    pdf_bytes: bytes,
    student_name: str,
    job_name: str,
    duplex: bool = True,
    copies: int = 1,
    ip: str = "172.16.4.9",
    port: int = 9100,
    timeout: float = 10.0,
    binding: str = "long",
    collate: bool = True
) -> dict:
    """
    Send job via RAW JetDirect socket (Port 9100) with PJL header.
    """
    payload = build_pjl_payload(pdf_bytes, student_name, job_name, duplex, copies, binding=binding, collate=collate)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.sendall(payload)
        return {
            "success": True,
            "protocol": "RAW Socket (9100)",
            "message": f"Job streamed to Canon printer for '{student_name}'.",
            "bytes_sent": len(payload)
        }
    finally:
        s.close()


def send_via_cups_cli(
    pdf_path: str,
    student_name: str,
    job_name: str,
    duplex: bool = True,
    copies: int = 1,
    printer_name: str = None,
    printer_ip: str = "172.16.4.9",
    binding: str = "long",
    collate: bool = True
) -> dict:
    """
    Send job via macOS / Linux CUPS CLI (`lp`).
    Searches lpstat -v for any printer device matching target IP.
    """
    if not printer_name and printer_ip:
        try:
            res = subprocess.run(["lpstat", "-v"], stdout=subprocess.PIPE, text=True, timeout=2)
            for line in res.stdout.splitlines():
                if printer_ip in line and "device for " in line:
                    parts = line.split("device for ")
                    if len(parts) > 1:
                        printer_name = parts[1].split(":")[0].strip()
                        break
        except Exception:
            pass

    if not printer_name:
        try:
            res = subprocess.run(["lpstat", "-d"], stdout=subprocess.PIPE, text=True, timeout=2)
            for line in res.stdout.splitlines():
                if "destination:" in line:
                    printer_name = line.split("destination:")[1].strip()
                    break
        except Exception:
            pass

    if not duplex:
        sides_val = "one-sided"
    elif str(binding).lower() == "short":
        sides_val = "two-sided-short-edge"
    else:
        sides_val = "two-sided-long-edge"

    cmd = ["lp"]
    if printer_name:
        cmd.extend(["-d", printer_name])
    cmd.extend([
        "-t", job_name,
        "-U", student_name,
        "-n", str(copies),
        "-o", f"sides={sides_val}",
        "-o", f"Collate={'True' if collate else 'False'}",
        pdf_path
    ])

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
    if proc.returncode == 0:
        return {
            "success": True,
            "protocol": f"CUPS lp CLI ({printer_name or 'default'})",
            "message": f"Dispatched via CUPS to '{printer_name or 'default'}' for '{student_name}': {proc.stdout.strip()}",
            "job_id": proc.stdout.strip()
        }
    else:
        raise RuntimeError(f"CUPS lp error: {proc.stderr.strip()}")


def build_ipp_print_request(
    pdf_bytes: bytes,
    student_name: str,
    job_name: str,
    duplex: bool = True,
    copies: int = 1,
    ip: str = "172.16.4.9",
    binding: str = "long",
    collate: bool = True
) -> bytes:
    """
    Construct binary IPP 2.0 Print-Job request (RFC 8010 / RFC 2910).
    """
    # IPP Header: version 2.0 (0x02, 0x00), operation Print-Job (0x0002), request-id (1)
    header = struct.pack(">BBHI", 2, 0, 0x0002, 1)

    # Operation attributes tag = 0x01
    body = b"\x01"

    def add_attr(tag, name, value):
        res = struct.pack(">B", tag)
        res += struct.pack(">H", len(name)) + name.encode("utf-8")
        if isinstance(value, str):
            val_bytes = value.encode("utf-8")
        elif isinstance(value, int):
            val_bytes = struct.pack(">i", value)
        elif isinstance(value, bytes):
            val_bytes = value
        else:
            val_bytes = str(value).encode("utf-8")
        res += struct.pack(">H", len(val_bytes)) + val_bytes
        return res

    # attributes-charset (0x47)
    body += add_attr(0x47, "attributes-charset", "utf-8")
    # attributes-natural-language (0x48)
    body += add_attr(0x48, "attributes-natural-language", "en")
    # printer-uri (0x45)
    body += add_attr(0x45, "printer-uri", f"ipp://{ip}:631/ipp/print")
    # requesting-user-name (0x42)
    body += add_attr(0x42, "requesting-user-name", student_name)
    # job-name (0x42)
    body += add_attr(0x42, "job-name", job_name)
    # document-format (0x49)
    body += add_attr(0x49, "document-format", "application/pdf")

    if not duplex:
        sides_val = "one-sided"
    elif str(binding).lower() == "short":
        sides_val = "two-sided-short-edge"
    else:
        sides_val = "two-sided-long-edge"
    body += add_attr(0x44, "sides", sides_val)
    body += add_attr(0x21, "copies", copies)
    handling = "separate-documents-collated-copies" if collate else "separate-documents-uncollated-copies"
    body += add_attr(0x44, "multiple-document-handling", handling)

    # End-of-attributes tag = 0x03
    body += b"\x03"

    return header + body + pdf_bytes


def send_via_ipp(
    pdf_bytes: bytes,
    student_name: str,
    job_name: str,
    duplex: bool = True,
    copies: int = 1,
    ip: str = "172.16.4.9",
    timeout: float = 10.0,
    binding: str = "long",
    collate: bool = True
) -> dict:
    """
    Send job via Internet Printing Protocol (IPP) over HTTP port 631.
    """
    req_data = build_ipp_print_request(pdf_bytes, student_name, job_name, duplex, copies, ip, binding=binding, collate=collate)
    url = f"http://{ip}:631/ipp/print"

    req = urllib.request.Request(
        url,
        data=req_data,
        headers={
            "Content-Type": "application/ipp",
            "User-Agent": "InkYard/1.0"
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp_data = resp.read()
        return {
            "success": True,
            "protocol": "IPP (RFC 8010)",
            "message": f"Dispatched via IPP to Canon printer for '{student_name}'.",
            "bytes_sent": len(req_data)
        }


def dispatch_print_job(
    pdf_path: str,
    student_name: str,
    job_name: str,
    duplex: bool = True,
    copies: int = 1,
    printer_ip: str = "172.16.4.9",
    preferred_protocol: str = "auto",
    binding: str = "long",
    collate: bool = True
) -> dict:
    """
    Universal print job dispatcher.
    Tries protocols in order of reliability for the Canon printer:
    1. LPD (Port 515) -> Proven to show author name and doc name on Canon hold queue
    2. CUPS lp (macOS) -> Local system queue if configured
    3. RAW Socket (Port 9100) -> Direct stream
    4. IPP (Port 631)
    5. Mock / Spool fallback if offline
    """
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    errors = []

    # Explicit protocols
    if preferred_protocol == "mock":
        return {
            "success": True,
            "protocol": "MOCK (Spool Saved)",
            "message": f"[Simulation] Job saved for '{student_name}' (Hold queue simulated).",
            "bytes_sent": len(pdf_bytes)
        }

    # Order of attempt:
    methods = []
    if preferred_protocol == "lpd" or preferred_protocol == "auto":
        methods.append(("LPD", lambda: send_via_lpd(pdf_bytes, student_name, job_name, duplex, copies, ip=printer_ip, binding=binding, collate=collate)))
    if preferred_protocol == "cups" or (preferred_protocol == "auto" and os.path.exists("/usr/bin/lp")):
        methods.append(("CUPS", lambda: send_via_cups_cli(pdf_path, student_name, job_name, duplex, copies, printer_ip=printer_ip, binding=binding, collate=collate)))
    if preferred_protocol == "socket" or preferred_protocol == "auto":
        methods.append(("RAW Socket", lambda: send_via_raw_socket(pdf_bytes, student_name, job_name, duplex, copies, ip=printer_ip, binding=binding, collate=collate)))
    if preferred_protocol == "ipp" or preferred_protocol == "auto":
        methods.append(("IPP", lambda: send_via_ipp(pdf_bytes, student_name, job_name, duplex, copies, ip=printer_ip, binding=binding, collate=collate)))

    for name, method in methods:
        try:
            res = method()
            if res.get("success"):
                return res
        except Exception as e:
            errors.append(f"{name}: {str(e)}")

    # If all network protocols failed, save to spool and return detailed error info
    return {
        "success": False,
        "protocol": "None",
        "message": f"Failed to reach printer at {printer_ip}. Errors: {'; '.join(errors)}",
        "errors": errors
    }
