/**
 * Printer InkSaver - Frontend Application Logic
 * Apple-style minimalist UI, visual page selection sidebar, multi-file queue,
 * collapsible advanced settings, dark mode manual toggle, and Canon printer dispatch.
 */

document.addEventListener("DOMContentLoaded", () => {
  // State
  let uploadedDocs = [];
  let currentDoc = null;
  let currentPage = 1;
  let currentMode = "eco";
  let selectedPages = new Set(); // 1-indexed page numbers
  
  // Advanced Settings State
  let currentBinding = "long"; // "long" | "short"
  let currentCollate = true;
  let currentInvertColor = false;
  let currentNup = 1; // 1 | 2 | 4

  let printerOnline = true;
  let printerIp = "172.16.4.9";
  let adsList = [];
  let currentAdIndex = 0;

  // Elements - Header & Theme
  const themeLightBtn = document.getElementById("themeLightBtn");
  const themeDarkBtn = document.getElementById("themeDarkBtn");
  const themeAutoBtn = document.getElementById("themeAutoBtn");
  const printerStatusDot = document.getElementById("printerStatusDot");
  const printerStatusText = document.getElementById("printerStatusText");
  const openConnectBtn = document.getElementById("openConnectBtn");
  const openStatsBtn = document.getElementById("openStatsBtn");
  const heroPortalUrl = document.getElementById("heroPortalUrl");
  const networkBadge = document.getElementById("networkBadge");

  // Elements - Upload & Queue
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const docQueueSection = document.getElementById("docQueueSection");
  const docQueueList = document.getElementById("docQueueList");
  const addMoreFilesBtn = document.getElementById("addMoreFilesBtn");
  const queueBadge = document.getElementById("queueBadge");
  const docPill = document.getElementById("docPill");
  const docName = document.getElementById("docName");
  const docDetails = document.getElementById("docDetails");
  const removeDocBtn = document.getElementById("removeDocBtn");

  // Elements - Sidebar Page Gallery
  const pageSidebar = document.getElementById("pageSidebar");
  const sidebarPageCount = document.getElementById("sidebarPageCount");
  const selectAllPagesBtn = document.getElementById("selectAllPagesBtn");
  const deselectAllPagesBtn = document.getElementById("deselectAllPagesBtn");
  const sidebarEmptyState = document.getElementById("sidebarEmptyState");
  const pageThumbnailGallery = document.getElementById("pageThumbnailGallery");

  // Elements - Live Preview
  const previewContainer = document.getElementById("previewContainer");
  const previewBox = document.getElementById("previewBox");
  const origImg = document.getElementById("origImg");
  const procImg = document.getElementById("procImg");
  const splitSlider = document.getElementById("splitSlider");
  const pageStepperLabel = document.getElementById("pageStepperLabel");
  const prevPageBtn = document.getElementById("prevPageBtn");
  const nextPageBtn = document.getElementById("nextPageBtn");
  const inkSavedBadge = document.getElementById("inkSavedBadge");

  // Elements - Print Details
  const studentNameInput = document.getElementById("studentName");
  const jobNameInput = document.getElementById("jobName");
  const duplexToggle = document.getElementById("duplexToggle");
  const pageRangeInput = document.getElementById("pageRange");
  const copiesInput = document.getElementById("copiesInput");
  const printerIpInput = document.getElementById("printerIp");

  // Elements - Advanced Settings Accordion
  const advancedSettingsCard = document.getElementById("advancedSettingsCard");
  const advancedSettingsToggle = document.getElementById("advancedSettingsToggle");
  const advancedSummary = document.getElementById("advancedSummary");
  const bindingEdgeControl = document.getElementById("bindingEdgeControl");
  const invertColorToggle = document.getElementById("invertColorToggle");
  const collateControl = document.getElementById("collateControl");
  const nupControl = document.getElementById("nupControl");

  // Elements - Eco Ticker
  const metricInk = document.getElementById("metricInk");
  const metricSheets = document.getElementById("metricSheets");
  const metricTrees = document.getElementById("metricTrees");
  const propagandaQuote = document.getElementById("propagandaQuote");

  // Elements - Actions
  const printBtn = document.getElementById("printBtn");
  const batchPrintBtn = document.getElementById("batchPrintBtn");
  const batchCountBadge = document.getElementById("batchCountBadge");
  const downloadBtn = document.getElementById("downloadBtn");
  const toast = document.getElementById("toast");

  // Modals
  const successModal = document.getElementById("successModal");
  const modalStudentName = document.getElementById("modalStudentName");
  const modalJobName = document.getElementById("modalJobName");
  const modalInkSaved = document.getElementById("modalInkSaved");
  const modalPrinterIp = document.getElementById("modalPrinterIp");
  const closeModalBtn = document.getElementById("closeModalBtn");

  const statsModal = document.getElementById("statsModal");
  const closeStatsBtn = document.getElementById("closeStatsBtn");

  const connectModal = document.getElementById("connectModal");
  const closeConnectModalBtn = document.getElementById("closeConnectModalBtn");
  const copyUrlBtn = document.getElementById("copyUrlBtn");
  const printPosterBtn = document.getElementById("printPosterBtn");
  const connectModalUrl = document.getElementById("connectModalUrl");
  const qrCanvasContainer = document.getElementById("qrCanvasContainer");

  const adModal = document.getElementById("adModal");
  const openAdModalBtn = document.getElementById("openAdModalBtn");
  const closeAdModalBtn = document.getElementById("closeAdModalBtn");
  const submitAdBtn = document.getElementById("submitAdBtn");
  const newAdTitle = document.getElementById("newAdTitle");
  const newAdTagline = document.getElementById("newAdTagline");
  const newAdDesc = document.getElementById("newAdDesc");
  const newAdContact = document.getElementById("newAdContact");
  const newAdBadge = document.getElementById("newAdBadge");
  const adBadge = document.getElementById("adBadge");
  const adTitle = document.getElementById("adTitle");
  const adTagline = document.getElementById("adTagline");
  const adDesc = document.getElementById("adDesc");
  const adContact = document.getElementById("adContact");
  const prevAdBtn = document.getElementById("prevAdBtn");
  const nextAdBtn = document.getElementById("nextAdBtn");

  // =========================================================================
  // 1. Theme Management (Light / Dark / Auto Manual Switcher)
  // =========================================================================
  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") {
      document.documentElement.setAttribute("data-theme", theme);
    } else {
      document.documentElement.setAttribute("data-theme", "auto");
    }
    localStorage.setItem("inkyard_theme", theme);
    localStorage.setItem("inksaver_theme", theme);
    
    // Update theme switcher buttons
    [themeLightBtn, themeDarkBtn, themeAutoBtn].forEach(btn => {
      if (btn) btn.classList.remove("active");
    });
    if (theme === "light" && themeLightBtn) themeLightBtn.classList.add("active");
    else if (theme === "dark" && themeDarkBtn) themeDarkBtn.classList.add("active");
    else if (themeAutoBtn) themeAutoBtn.classList.add("active");
  }

  const savedTheme = localStorage.getItem("inkyard_theme") || localStorage.getItem("inksaver_theme") || "auto";
  applyTheme(savedTheme);

  if (themeLightBtn) themeLightBtn.addEventListener("click", () => applyTheme("light"));
  if (themeDarkBtn) themeDarkBtn.addEventListener("click", () => applyTheme("dark"));
  if (themeAutoBtn) themeAutoBtn.addEventListener("click", () => applyTheme("auto"));

  // =========================================================================
  // 2. Student Name & Network Portal Info
  // =========================================================================
  const savedName = localStorage.getItem("inkyard_student_name") || localStorage.getItem("inksaver_student_name");
  if (savedName && studentNameInput) {
    studentNameInput.value = savedName;
  }
  if (studentNameInput) {
    studentNameInput.addEventListener("input", (e) => {
      const val = e.target.value.trim();
      localStorage.setItem("inkyard_student_name", val);
      localStorage.setItem("inksaver_student_name", val);
    });
  }

  async function fetchNetworkInfo() {
    try {
      const res = await fetch("/api/network_info");
      if (res.ok) {
        const data = await res.json();
        if (heroPortalUrl) heroPortalUrl.textContent = data.portal_url;
        if (connectModalUrl) connectModalUrl.value = data.portal_url;
        if (typeof renderQrCode === "function") {
          renderQrCode(data.portal_url);
        }
      }
    } catch (e) {
      console.warn("Could not fetch network info:", e);
    }
  }
  fetchNetworkInfo();

  // Printer status polling
  async function checkStatus() {
    try {
      const ip = printerIpInput ? printerIpInput.value.trim() : printerIp;
      const res = await fetch(`/api/printer_status?ip=${encodeURIComponent(ip)}`);
      const data = await res.json();
      printerOnline = data.online;
      if (data.online) {
        printerStatusDot.classList.remove("offline");
        printerStatusText.textContent = `Canon ${ip} Online (${data.latency_ms}ms)`;
      } else {
        printerStatusDot.classList.add("offline");
        printerStatusText.textContent = `Canon ${ip} Offline (Simulation Mode)`;
      }
    } catch (e) {
      printerStatusDot.classList.add("offline");
      printerStatusText.textContent = `Canon Offline`;
    }
  }
  checkStatus();
  setInterval(checkStatus, 15000);

  // =========================================================================
  // 3. Batch File Upload & Document Queue Management
  // =========================================================================
  if (dropZone) {
    ["dragenter", "dragover"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
      });
    });

    dropZone.addEventListener("drop", (e) => {
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleBatchUpload(files);
      }
    });

    dropZone.addEventListener("click", () => fileInput.click());
  }

  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files.length > 0) {
        handleBatchUpload(e.target.files);
      }
    });
  }

  if (addMoreFilesBtn) {
    addMoreFilesBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  async function handleBatchUpload(fileList) {
    const files = Array.from(fileList);
    if (!files.length) return;

    showToast(`Uploading and analyzing ${files.length} document${files.length > 1 ? "s" : ""}...`);
    dropZone.style.opacity = "0.5";

    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));

    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      dropZone.style.opacity = "1";

      if (!res.ok || data.error) {
        showToast(data.error || "Upload failed", true);
        return;
      }

      const newDocs = data.docs && data.docs.length > 0 ? data.docs : [data];
      newDocs.forEach((d) => {
        // Prevent duplicate doc_id
        if (!uploadedDocs.some((existing) => existing.doc_id === d.doc_id)) {
          uploadedDocs.push(d);
        }
      });

      // Set active doc to the first of newly added or first in queue
      if (!currentDoc || !uploadedDocs.some(d => d.doc_id === currentDoc.doc_id)) {
        setActiveDocument(newDocs[0]);
      } else {
        renderDocQueue();
      }

      showToast(`Added ${newDocs.length} document${newDocs.length > 1 ? "s" : ""} to queue!`);
    } catch (err) {
      dropZone.style.opacity = "1";
      showToast("Network error during document upload", true);
    } finally {
      fileInput.value = "";
    }
  }

  function saveCurrentDocState() {
    if (currentDoc) {
      currentDoc.selectedPages = new Set(selectedPages);
      currentDoc.pageRange = pageRangeInput.value;
      if (jobNameInput) currentDoc.jobName = jobNameInput.value;
    }
  }

  function setActiveDocument(doc) {
    if (currentDoc && currentDoc.doc_id !== doc.doc_id) {
      saveCurrentDocState();
    }

    currentDoc = doc;
    currentPage = 1;

    // Restore or initialize selected pages for this document
    if (doc.selectedPages && doc.selectedPages.size > 0) {
      selectedPages = new Set(doc.selectedPages);
      pageRangeInput.value = doc.pageRange || (selectedPages.size === doc.total_pages ? "all" : "");
    } else {
      selectedPages = new Set();
      for (let p = 1; p <= doc.total_pages; p++) {
        selectedPages.add(p);
      }
      doc.selectedPages = new Set(selectedPages);
      doc.pageRange = "all";
      pageRangeInput.value = "all";
    }

    // Update Print Details
    if (jobNameInput) jobNameInput.value = doc.jobName || doc.clean_title;
    if (docName) docName.textContent = doc.filename;
    if (docDetails) docDetails.textContent = `${doc.total_pages} Page${doc.total_pages > 1 ? "s" : ""} • ${doc.file_size}`;
    
    // Enable buttons
    printBtn.disabled = false;
    downloadBtn.disabled = false;

    // Render components
    renderDocQueue();
    renderSidebarThumbnails(doc);
    
    // If current mode matches default eco and not inverted, show preview immediately, otherwise fetch
    if (currentMode === "eco" && !currentInvertColor && doc.preview) {
      renderPreview(doc.preview);
    } else {
      fetchPreview();
    }
    updateEcoTicker();
  }

  function renderDocQueue() {
    if (!uploadedDocs.length) {
      docQueueSection.style.display = "none";
      if (docPill) docPill.classList.remove("active");
      previewContainer.classList.remove("active");
      dropZone.style.display = "block";
      dropZone.classList.remove("compact");
      if (queueBadge) queueBadge.style.display = "none";
      if (batchPrintBtn) batchPrintBtn.style.display = "none";
      printBtn.disabled = true;
      downloadBtn.disabled = true;
      currentDoc = null;
      renderSidebarThumbnails(null);
      updateEcoTicker();
      return;
    }

    docQueueSection.style.display = "block";
    if (docPill) docPill.classList.remove("active");
    dropZone.classList.add("compact");
    if (queueBadge) {
      queueBadge.style.display = "inline-block";
      queueBadge.textContent = `${uploadedDocs.length} file${uploadedDocs.length > 1 ? "s" : ""} in queue`;
    }

    if (batchPrintBtn && batchCountBadge) {
      if (uploadedDocs.length > 1) {
        batchPrintBtn.style.display = "flex";
        batchCountBadge.textContent = uploadedDocs.length;
      } else {
        batchPrintBtn.style.display = "none";
      }
    }

    docQueueList.innerHTML = "";
    uploadedDocs.forEach((doc, idx) => {
      const isActive = currentDoc && doc.doc_id === currentDoc.doc_id;
      const item = document.createElement("div");
      item.className = `doc-queue-item ${isActive ? "active" : ""}`;
      item.innerHTML = `
        <div class="queue-item-meta">
          <svg class="queue-file-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <div class="queue-item-info">
            <div class="queue-item-name" title="${doc.filename}">${doc.filename}</div>
            <div class="queue-item-sub">${doc.total_pages} page${doc.total_pages > 1 ? "s" : ""} • ${doc.file_size}</div>
          </div>
        </div>
        <div class="queue-item-actions">
          ${isActive ? '<span class="queue-active-badge">Active</span>' : ""}
          <button type="button" class="queue-remove-btn" title="Remove file" data-id="${doc.doc_id}">×</button>
        </div>
      `;

      item.addEventListener("click", (e) => {
        if (e.target.classList.contains("queue-remove-btn")) return;
        setActiveDocument(doc);
      });

      const removeBtn = item.querySelector(".queue-remove-btn");
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        removeDocument(doc.doc_id);
      });

      docQueueList.appendChild(item);
    });
  }

  function removeDocument(docId) {
    uploadedDocs = uploadedDocs.filter(d => d.doc_id !== docId);
    if (currentDoc && currentDoc.doc_id === docId) {
      if (uploadedDocs.length > 0) {
        setActiveDocument(uploadedDocs[0]);
      } else {
        renderDocQueue();
      }
    } else {
      renderDocQueue();
    }
    showToast("Document removed from queue");
  }

  if (removeDocBtn) {
    removeDocBtn.addEventListener("click", () => {
      if (currentDoc) removeDocument(currentDoc.doc_id);
    });
  }

  // =========================================================================
  // 4. Apple-Style Visual Page Selection GUI in Sidebar
  // =========================================================================
  function renderSidebarThumbnails(doc) {
    if (!doc || !doc.total_pages) {
      sidebarEmptyState.style.display = "block";
      pageThumbnailGallery.style.display = "none";
      sidebarPageCount.textContent = "0 pages";
      return;
    }

    sidebarEmptyState.style.display = "none";
    pageThumbnailGallery.style.display = "flex";
    updateSidebarCount();

    pageThumbnailGallery.innerHTML = "";

    for (let p = 1; p <= doc.total_pages; p++) {
      const isSelected = selectedPages.has(p);
      const isPreviewActive = p === currentPage;

      const card = document.createElement("div");
      card.className = `page-thumb-card ${isSelected ? "" : "deselected"} ${isPreviewActive ? "preview-active" : ""}`;
      card.dataset.page = p;

      card.innerHTML = `
        <div class="page-thumb-paper" title="Click to view Page ${p}">
          <img src="/api/thumbnail/${doc.doc_id}/${p}" class="page-thumb-img" alt="Page ${p}" loading="lazy">
          <div class="floating-page-pill" title="Toggle Page ${p} inclusion in print job">
            <div class="pill-check-disc ${isSelected ? "" : "unchecked"}">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </div>
            <span class="pill-page-text">Page ${p} of ${doc.total_pages}</span>
          </div>
        </div>
      `;

      // 1. Clicking the floating pill or checkmark toggles whether that page is printed
      const pill = card.querySelector(".floating-page-pill");
      pill.addEventListener("click", (e) => {
        e.stopPropagation();
        togglePageSelection(p, card);
      });

      // 2. Clicking the paper thumbnail switches the live comparison preview to that page
      const paper = card.querySelector(".page-thumb-paper");
      paper.addEventListener("click", () => {
        currentPage = p;
        updatePreviewActiveThumbnail();
        fetchPreview();
      });

      pageThumbnailGallery.appendChild(card);
    }
  }

  function togglePageSelection(p, card) {
    if (!currentDoc) return;
    if (selectedPages.has(p)) {
      selectedPages.delete(p);
      card.classList.add("deselected");
      const disc = card.querySelector(".pill-check-disc");
      if (disc) disc.classList.add("unchecked");
    } else {
      selectedPages.add(p);
      card.classList.remove("deselected");
      const disc = card.querySelector(".pill-check-disc");
      if (disc) disc.classList.remove("unchecked");
    }

    // Sync with pageRange input text & current doc state
    syncPageRangeFromSet();
    if (currentDoc) {
      currentDoc.selectedPages = new Set(selectedPages);
      currentDoc.pageRange = pageRangeInput.value;
    }
    updateSidebarCount();
    updateEcoTicker();

    // Also navigate preview to this page
    if (currentPage !== p) {
      currentPage = p;
      updatePreviewActiveThumbnail();
      fetchPreview();
    }
  }

  function updateSidebarCount() {
    if (!currentDoc) {
      sidebarPageCount.textContent = "0 pages";
      return;
    }
    sidebarPageCount.textContent = `${selectedPages.size} of ${currentDoc.total_pages} selected`;
  }

  function updatePreviewActiveThumbnail() {
    const cards = pageThumbnailGallery.querySelectorAll(".page-thumb-card");
    cards.forEach((card) => {
      const p = parseInt(card.dataset.page);
      if (p === currentPage) {
        card.classList.add("preview-active");
      } else {
        card.classList.remove("preview-active");
      }
    });
  }

  function syncPageRangeFromSet() {
    if (!currentDoc) return;
    if (selectedPages.size === currentDoc.total_pages) {
      pageRangeInput.value = "all";
      return;
    }
    if (selectedPages.size === 0) {
      pageRangeInput.value = "";
      return;
    }

    const sorted = Array.from(selectedPages).sort((a, b) => a - b);
    const ranges = [];
    let start = sorted[0];
    let end = sorted[0];

    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i] === end + 1) {
        end = sorted[i];
      } else {
        ranges.push(start === end ? `${start}` : `${start}-${end}`);
        start = sorted[i];
        end = sorted[i];
      }
    }
    ranges.push(start === end ? `${start}` : `${start}-${end}`);
    pageRangeInput.value = ranges.join(", ");
  }

  function syncSetFromPageRangeText() {
    if (!currentDoc) return;
    const text = pageRangeInput.value.trim().toLowerCase();
    selectedPages = new Set();

    if (text === "all" || text === "*") {
      for (let p = 1; p <= currentDoc.total_pages; p++) selectedPages.add(p);
    } else if (text === "") {
      // Intentionally empty when user clears or clicks Deselect All
    } else {
      const parts = text.split(",");
      parts.forEach((part) => {
        part = part.trim();
        if (part.includes("-")) {
          const [s, e] = part.split("-").map(Number);
          if (!isNaN(s) && !isNaN(e)) {
            for (let i = Math.max(1, s); i <= Math.min(currentDoc.total_pages, e); i++) {
              selectedPages.add(i);
            }
          }
        } else if (Number(part)) {
          const p = Number(part);
          if (p >= 1 && p <= currentDoc.total_pages) selectedPages.add(p);
        }
      });
    }

    if (currentDoc) {
      currentDoc.selectedPages = new Set(selectedPages);
      currentDoc.pageRange = pageRangeInput.value;
    }

    // Update thumbnail cards
    const cards = pageThumbnailGallery.querySelectorAll(".page-thumb-card");
    cards.forEach((card) => {
      const p = parseInt(card.dataset.page);
      const disc = card.querySelector(".pill-check-disc");
      if (selectedPages.has(p)) {
        card.classList.remove("deselected");
        if (disc) disc.classList.remove("unchecked");
      } else {
        card.classList.add("deselected");
        if (disc) disc.classList.add("unchecked");
      }
    });

    updateSidebarCount();
    updateEcoTicker();
  }

  if (selectAllPagesBtn) {
    selectAllPagesBtn.addEventListener("click", () => {
      if (!currentDoc) return;
      selectedPages = new Set();
      for (let p = 1; p <= currentDoc.total_pages; p++) selectedPages.add(p);
      pageRangeInput.value = "all";
      currentDoc.selectedPages = new Set(selectedPages);
      currentDoc.pageRange = "all";
      const cards = pageThumbnailGallery.querySelectorAll(".page-thumb-card");
      cards.forEach((card) => {
        card.classList.remove("deselected");
        const disc = card.querySelector(".pill-check-disc");
        if (disc) disc.classList.remove("unchecked");
      });
      updateSidebarCount();
      updateEcoTicker();
    });
  }

  if (deselectAllPagesBtn) {
    deselectAllPagesBtn.addEventListener("click", () => {
      if (!currentDoc) return;
      selectedPages.clear();
      pageRangeInput.value = "";
      currentDoc.selectedPages = new Set(selectedPages);
      currentDoc.pageRange = "";
      const cards = pageThumbnailGallery.querySelectorAll(".page-thumb-card");
      cards.forEach((card) => {
        card.classList.add("deselected");
        const disc = card.querySelector(".pill-check-disc");
        if (disc) disc.classList.add("unchecked");
      });
      updateSidebarCount();
      updateEcoTicker();
    });
  }

  pageRangeInput.addEventListener("input", syncSetFromPageRangeText);

  // =========================================================================
  // 5. Collapsible Advanced Settings (Binding, Invert Color, Collate, N-Up)
  // =========================================================================
  if (advancedSettingsToggle) {
    advancedSettingsToggle.addEventListener("click", () => {
      advancedSettingsCard.classList.toggle("open");
    });
  }

  function updateAdvancedSummary() {
    const bindLabel = currentBinding === "long" ? "Long edge" : "Short edge";
    const collLabel = currentCollate ? "Collate" : "Group";
    const nupLabel = `${currentNup}-Up`;
    const invLabel = currentInvertColor ? " • Negative" : "";
    advancedSummary.textContent = `${bindLabel} • ${collLabel} • ${nupLabel}${invLabel}`;
  }

  // Ensure Inverse Color defaults to false / unchecked on page load
  if (invertColorToggle) {
    invertColorToggle.checked = false;
    currentInvertColor = false;
  }
  updateAdvancedSummary();

  // 1. Binding Edge Control
  if (bindingEdgeControl) {
    bindingEdgeControl.querySelectorAll(".segment-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        bindingEdgeControl.querySelectorAll(".segment-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentBinding = btn.dataset.binding || "long";
        updateAdvancedSummary();
      });
    });
  }

  // 2. Inverse Color Toggle
  if (invertColorToggle) {
    invertColorToggle.addEventListener("change", async (e) => {
      currentInvertColor = e.target.checked;
      updateAdvancedSummary();
      await fetchPreview(); // Refresh comparison preview immediately
      if (currentInvertColor && currentDoc) {
        // If current preview is available and has light background, show intelligent notification
        if (currentDoc.preview && currentDoc.preview.is_dark_bg === false) {
          showToast("Smart Protection: Document has a light background. White paper kept pure white to save ink! (浅色文档智能保护：自动保持纯白背景)");
        }
      }
    });
  }

  // 3. Collate Control
  if (collateControl) {
    collateControl.querySelectorAll(".segment-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        collateControl.querySelectorAll(".segment-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentCollate = btn.dataset.collate === "true";
        updateAdvancedSummary();
      });
    });
  }

  // 4. N-Up Pages Per Sheet Control
  if (nupControl) {
    nupControl.querySelectorAll(".segment-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        nupControl.querySelectorAll(".segment-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentNup = parseInt(btn.dataset.nup) || 1;
        updateAdvancedSummary();
        updateEcoTicker();
      });
    });
  }

  // =========================================================================
  // 6. Live Before/After Preview & Mode Selector
  // =========================================================================
  document.querySelectorAll(".mode-card").forEach((card) => {
    card.addEventListener("click", () => {
      document.querySelectorAll(".mode-card").forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
      currentMode = card.dataset.mode;
      fetchPreview();
      updateEcoTicker();
    });
  });

  duplexToggle.addEventListener("change", updateEcoTicker);
  copiesInput.addEventListener("input", updateEcoTicker);

  async function fetchPreview() {
    if (!currentDoc) return;
    try {
      const res = await fetch("/api/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doc_id: currentDoc.doc_id,
          page: currentPage,
          mode: currentMode,
          invert_color: currentInvertColor
        })
      });
      const data = await res.json();
      if (res.ok) {
        renderPreview(data);
      }
    } catch (e) {
      console.error("Preview fetch error:", e);
    }
  }

  function renderPreview(preview) {
    if (!preview) return;
    if (currentDoc) {
      currentDoc.preview = preview;
    }
    origImg.src = preview.orig_b64;
    procImg.src = preview.proc_b64;
    pageStepperLabel.textContent = `Page ${preview.page} of ${preview.total_pages}`;
    inkSavedBadge.textContent = `${preview.ink_saved_pct}% Ink Spared`;
    
    prevPageBtn.disabled = preview.page <= 1;
    nextPageBtn.disabled = preview.page >= preview.total_pages;
    
    previewContainer.classList.add("active");
    splitSlider.value = 50;
    if (previewBox) {
      previewBox.style.setProperty("--split-pos", "50%");
    }
  }

  splitSlider.addEventListener("input", (e) => {
    const val = e.target.value;
    if (previewBox) {
      previewBox.style.setProperty("--split-pos", `${val}%`);
    }
  });

  prevPageBtn.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      updatePreviewActiveThumbnail();
      fetchPreview();
    }
  });

  nextPageBtn.addEventListener("click", () => {
    if (currentDoc && currentPage < currentDoc.total_pages) {
      currentPage++;
      updatePreviewActiveThumbnail();
      fetchPreview();
    }
  });

  // =========================================================================
  // 7. Eco-Ticker & Sustainability Propaganda Calculations
  // =========================================================================
  function updateEcoTicker() {
    const totalPages = currentDoc ? currentDoc.total_pages : 1;
    let printedPages = selectedPages.size;
    if (!currentDoc) printedPages = 1;

    const copies = Math.max(1, parseInt(copiesInput.value) || 1);
    const totalJobPages = printedPages * copies;
    const isDuplex = duplexToggle.checked;
    
    // Account for N-up multi-page per sheet reduction
    let physicalSheetsBeforeDuplex = Math.ceil(totalJobPages / currentNup);
    let physicalSheetsUsed = isDuplex ? Math.ceil(physicalSheetsBeforeDuplex / 2) : physicalSheetsBeforeDuplex;
    let sheetsSaved = Math.max(0, totalJobPages - physicalSheetsUsed);
    
    const modePctMap = {
      normal: 0.0,
      eco: 25.0,
      matrix: 50.0,
      slide_clean: 60.0,
      line_art: 75.0
    };
    let pct = modePctMap[currentMode] !== undefined ? modePctMap[currentMode] : 25.0;
    if (currentInvertColor && pct < 50.0) pct = 50.0; // Inverting dark docs spares huge toner
    
    const inkSavedMl = (totalJobPages * 0.05 * (pct / 100.0)).toFixed(2);
    const trees = (sheetsSaved / 8333.0).toFixed(4);

    metricInk.textContent = `~${inkSavedMl} mL`;
    metricSheets.textContent = `${sheetsSaved} sheets`;
    metricTrees.textContent = `${trees}`;

    const slogans = [
      `🗳️ PROMISE TO THE PLANET: By choosing Double-Sided + ${currentMode.toUpperCase()}${currentNup > 1 ? ` + ${currentNup}-Up` : ""}, you spared ~${inkSavedMl} mL of toner and saved ${sheetsSaved} sheets. Our campus endorses your green ballot!`,
      `🌱 REVOLUTIONARY RESTRAINT: You just prevented ${sheetsSaved} sheets of virgin timber from unnecessary consumption. Nature awards you full eco-honors.`,
      `⚡ ZERO-DRIVER INDEPENDENCE: Bypassed \$99 developer monopolies and bloated manufacturer drivers with pure, clean, lightweight web engineering.`,
      `🌊 ECO-TONER VICTORY: Choosing ${currentMode.toUpperCase()} mode keeps toxic plastic toner cartridges out of campus dumpsters. If the whole school followed your lead, we save thousands of liters of synthetic resin!`
    ];
    
    const sloganIndex = Math.abs((totalJobPages * 7 + (isDuplex ? 3 : 1) + currentNup) % slogans.length);
    propagandaQuote.textContent = `"${slogans[sloganIndex]}"`;
  }

  // =========================================================================
  // 8. Print Dispatcher & Batch Printing
  // =========================================================================
  printBtn.addEventListener("click", async () => {
    if (!currentDoc) return;

    if (selectedPages.size === 0) {
      showToast("Please select at least one page to print!", true);
      return;
    }

    const studentName = studentNameInput.value.trim();
    if (!studentName) {
      studentNameInput.focus();
      studentNameInput.style.borderColor = "#ff3b30";
      setTimeout(() => studentNameInput.style.borderColor = "", 2000);
      showToast("Please enter your Student Name so your job shows on the Canon screen!", true);
      return;
    }

    const jobName = jobNameInput.value.trim() || currentDoc.clean_title;
    const isDuplex = duplexToggle.checked;
    const pageRange = pageRangeInput.value.trim() || (selectedPages.size === currentDoc.total_pages ? "all" : Array.from(selectedPages).sort((a,b)=>a-b).join(","));
    const copies = parseInt(copiesInput.value) || 1;
    const ip = printerIpInput ? printerIpInput.value.trim() : printerIp;

    printBtn.disabled = true;
    printBtn.innerHTML = '<span class="spinner"></span> Dispatching to Canon...';

    try {
      const res = await fetch("/api/print", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doc_id: currentDoc.doc_id,
          student_name: studentName,
          job_name: jobName,
          ink_mode: currentMode,
          page_range: pageRange,
          duplex: isDuplex,
          copies: copies,
          printer_ip: ip,
          binding: currentBinding,
          collate: currentCollate,
          invert_color: currentInvertColor,
          nup: currentNup
        })
      });
      const data = await res.json();
      printBtn.disabled = false;
      printBtn.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 6 2 18 2 18 9"></polyline>
          <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
          <rect x="6" y="14" width="12" height="8"></rect>
        </svg>
        Send to Canon Printer
      `;

      if (data.success || data.dispatch?.success) {
        modalStudentName.textContent = studentName;
        modalJobName.textContent = jobName;
        modalInkSaved.textContent = `${data.metrics?.avg_ink_saved_pct || 50}% (${data.metrics?.est_ink_saved_ml || 0.1} mL)`;
        modalPrinterIp.textContent = ip;
        successModal.classList.add("active");
        showToast("Print job dispatched to Canon hold queue!");
      } else {
        showToast(data.dispatch?.message || "Printer communication error", true);
      }
    } catch (err) {
      printBtn.disabled = false;
      printBtn.innerHTML = "Send to Canon Printer";
      showToast("Print error: " + err.message, true);
    }
  });

  // Batch Print All Queued Documents
  if (batchPrintBtn) {
    batchPrintBtn.addEventListener("click", async () => {
      if (!uploadedDocs.length) return;

      const studentName = studentNameInput.value.trim();
      if (!studentName) {
        studentNameInput.focus();
        studentNameInput.style.borderColor = "#ff3b30";
        setTimeout(() => studentNameInput.style.borderColor = "", 2000);
        showToast("Please enter your Student Name so jobs show on the Canon screen!", true);
        return;
      }

      saveCurrentDocState();
      const isDuplex = duplexToggle.checked;
      const copies = parseInt(copiesInput.value) || 1;
      const ip = printerIpInput ? printerIpInput.value.trim() : printerIp;

      batchPrintBtn.disabled = true;
      batchPrintBtn.innerHTML = '<span class="spinner"></span> Dispatching All Jobs...';

      const jobs = uploadedDocs.map((doc) => {
        let pRange = doc.pageRange;
        if (!pRange) {
          pRange = (doc.selectedPages && doc.selectedPages.size === doc.total_pages) ? "all" : (doc.selectedPages ? Array.from(doc.selectedPages).sort((a,b)=>a-b).join(",") : "all");
        }
        return {
          doc_id: doc.doc_id,
          student_name: studentName,
          job_name: doc.jobName || doc.clean_title,
          ink_mode: currentMode,
          page_range: pRange || "all",
          duplex: isDuplex,
          copies: copies,
          printer_ip: ip,
          binding: currentBinding,
          collate: currentCollate,
          invert_color: currentInvertColor,
          nup: currentNup
        };
      });

      try {
        const res = await fetch("/api/batch_print", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ jobs: jobs })
        });
        const data = await res.json();
        batchPrintBtn.disabled = false;
        batchPrintBtn.innerHTML = `
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
            <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
          </svg>
          Print All Queued Documents (<span id="batchCountBadge">${uploadedDocs.length}</span>)
        `;

        if (data.success || data.results?.some(r => r.success)) {
          modalStudentName.textContent = studentName;
          modalJobName.textContent = `${uploadedDocs.length} Documents`;
          modalInkSaved.textContent = `Batch Eco Processing Complete`;
          modalPrinterIp.textContent = ip;
          successModal.classList.add("active");
          showToast(`All ${uploadedDocs.length} print jobs queued for '${studentName}'!`);
        } else {
          showToast("Batch printing encountered an error", true);
        }
      } catch (err) {
        batchPrintBtn.disabled = false;
        batchPrintBtn.textContent = `Print All Queued Documents (${uploadedDocs.length})`;
        showToast("Batch print error: " + err.message, true);
      }
    });
  }

  // Download Processed PDF
  downloadBtn.addEventListener("click", async () => {
    if (!currentDoc) return;

    if (selectedPages.size === 0) {
      showToast("Please select at least one page to download!", true);
      return;
    }

    downloadBtn.disabled = true;
    downloadBtn.textContent = "Processing PDF...";

    const pageRange = pageRangeInput.value.trim() || (selectedPages.size === currentDoc.total_pages ? "all" : Array.from(selectedPages).sort((a,b)=>a-b).join(","));

    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doc_id: currentDoc.doc_id,
          ink_mode: currentMode,
          page_range: pageRange,
          clean_name: currentDoc.clean_title,
          invert_color: currentInvertColor,
          nup: currentNup
        })
      });

      if (!res.ok) {
        showToast("Download failed", true);
        return;
      }

      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `${currentDoc.clean_title}_${currentMode}_inkyard.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
      showToast("Ink-saved PDF downloaded!");
    } catch (e) {
      showToast("Download error: " + e.message, true);
    } finally {
      downloadBtn.disabled = false;
      downloadBtn.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
        Download Processed PDF
      `;
    }
  });

  // =========================================================================
  // 9. Connect Device / QR Code Modal
  // =========================================================================
  function renderQrCode(targetUrl) {
    if (!qrCanvasContainer || !window.QRCode) return;
    const url = targetUrl || (heroPortalUrl && heroPortalUrl.textContent.trim().startsWith("http")
      ? heroPortalUrl.textContent.trim()
      : (connectModalUrl && connectModalUrl.value.trim().startsWith("http") ? connectModalUrl.value.trim() : window.location.href));
    if (connectModalUrl && (!connectModalUrl.value || targetUrl)) {
      connectModalUrl.value = url;
    }
    
    qrCanvasContainer.innerHTML = "";
    new window.QRCode(qrCanvasContainer, {
      text: url,
      width: 240,
      height: 240,
      colorDark: "#000000",
      colorLight: "#ffffff",
      correctLevel: (window.QRCode.CorrectLevel && window.QRCode.CorrectLevel.M !== undefined) ? window.QRCode.CorrectLevel.M : 0
    });
  }

  function showConnectModal() {
    let url = (heroPortalUrl && heroPortalUrl.textContent.trim().startsWith("http"))
      ? heroPortalUrl.textContent.trim()
      : (connectModalUrl && connectModalUrl.value.trim().startsWith("http") ? connectModalUrl.value.trim() : window.location.href);
    if (connectModalUrl) connectModalUrl.value = url;
    
    if (!qrCanvasContainer || qrCanvasContainer.children.length === 0) {
      renderQrCode(url);
    }
    connectModal.classList.add("active");
  }

  // Pre-generate QR code on initial page load
  try {
    renderQrCode();
  } catch (e) {
    console.warn("Initial QR render skipped:", e);
  }

  if (openConnectBtn) openConnectBtn.addEventListener("click", showConnectModal);
  if (networkBadge) networkBadge.addEventListener("click", () => {
    const url = heroPortalUrl ? heroPortalUrl.textContent.trim() : window.location.href;
    navigator.clipboard.writeText(url).then(() => {
      showToast("Portal link copied to clipboard!");
    }).catch(() => {
      showConnectModal();
    });
  });

  if (closeConnectModalBtn) closeConnectModalBtn.addEventListener("click", () => {
    connectModal.classList.remove("active");
  });

  if (copyUrlBtn) copyUrlBtn.addEventListener("click", () => {
    if (connectModalUrl) {
      connectModalUrl.select();
      navigator.clipboard.writeText(connectModalUrl.value);
      showToast("Portal link copied to clipboard!");
    }
  });

  if (printPosterBtn) printPosterBtn.addEventListener("click", () => {
    window.print();
  });

  // =========================================================================
  // 10. Student Announcements / Campus Notice Board
  // =========================================================================
  async function loadAds() {
    try {
      const res = await fetch("/api/ads");
      if (res.ok) {
        adsList = await res.json();
        currentAdIndex = 0;
        renderCurrentAd();
      }
    } catch (e) {
      console.warn("Could not load student ads:", e);
    }
  }

  function renderCurrentAd() {
    if (!adsList || adsList.length === 0) return;
    const ad = adsList[currentAdIndex % adsList.length];
    if (adBadge) adBadge.textContent = ad.badge || "Club Notice";
    if (adTitle) adTitle.textContent = ad.title;
    if (adTagline) adTagline.textContent = ad.tagline || "";
    if (adDesc) adDesc.textContent = ad.desc || "";
    if (adContact) adContact.textContent = `Contact: ${ad.contact || "@school"}`;
  }

  if (prevAdBtn) prevAdBtn.addEventListener("click", () => {
    if (adsList.length > 0) {
      currentAdIndex = (currentAdIndex - 1 + adsList.length) % adsList.length;
      renderCurrentAd();
    }
  });

  if (nextAdBtn) nextAdBtn.addEventListener("click", () => {
    if (adsList.length > 0) {
      currentAdIndex = (currentAdIndex + 1) % adsList.length;
      renderCurrentAd();
    }
  });

  setInterval(() => {
    if (adsList.length > 1) {
      currentAdIndex = (currentAdIndex + 1) % adsList.length;
      renderCurrentAd();
    }
  }, 14000);

  loadAds();

  if (openAdModalBtn) openAdModalBtn.addEventListener("click", () => adModal.classList.add("active"));
  if (closeAdModalBtn) closeAdModalBtn.addEventListener("click", () => adModal.classList.remove("active"));

  if (submitAdBtn) {
    submitAdBtn.addEventListener("click", async () => {
      const title = newAdTitle.value.trim();
      if (!title) {
        newAdTitle.focus();
        showToast("Please enter an event or project title!", true);
        return;
      }

      const payload = {
        title: title,
        tagline: newAdTagline.value.trim(),
        desc: newAdDesc.value.trim(),
        contact: newAdContact.value.trim() || "@campus",
        badge: newAdBadge.value
      };

      submitAdBtn.disabled = true;
      submitAdBtn.textContent = "Publishing...";

      try {
        const res = await fetch("/api/ads", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        submitAdBtn.disabled = false;
        submitAdBtn.textContent = "Publish Notice";

        if (res.ok) {
          adsList.unshift(data);
          currentAdIndex = 0;
          renderCurrentAd();
          adModal.classList.remove("active");
          newAdTitle.value = "";
          newAdTagline.value = "";
          newAdDesc.value = "";
          newAdContact.value = "";
          showToast("Notice posted to campus community board!");
        } else {
          showToast(data.error || "Failed to post notice", true);
        }
      } catch (e) {
        submitAdBtn.disabled = false;
        submitAdBtn.textContent = "Publish Notice";
        showToast("Error posting notice: " + e.message, true);
      }
    });
  }

  // =========================================================================
  // 11. Modal Closers & Toast
  // =========================================================================
  if (closeModalBtn) closeModalBtn.addEventListener("click", () => successModal.classList.remove("active"));
  
  if (openStatsBtn) {
    openStatsBtn.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/stats");
        const stats = await res.json();
        document.getElementById("statTotalJobs").textContent = stats.total_jobs;
        document.getElementById("statTotalPages").textContent = stats.total_pages;
        document.getElementById("statSheetsSaved").textContent = stats.total_sheets_saved;
        document.getElementById("statInkSaved").textContent = `${stats.total_ink_saved_ml} mL`;
        document.getElementById("statTreesSaved").textContent = stats.trees_saved;
        document.getElementById("statDuplexRate").textContent = `${stats.duplex_adoption_rate}%`;
        statsModal.classList.add("active");
      } catch (e) {
        showToast("Failed to load statistics", true);
      }
    });
  }

  // =========================================================================
  // 12. Easter Egg: Marquant Vahram Handwritten Signature Card
  // =========================================================================
  const easterEggModal = document.getElementById("easterEggModal");
  const closeEasterEggBtn = document.getElementById("closeEasterEggBtn");
  const brandLogo = document.getElementById("brandLogo");

  function triggerEasterEgg() {
    if (!easterEggModal) return;
    easterEggModal.classList.add("active");
    spawnEasterConfetti();
  }

  function closeEasterEgg() {
    if (easterEggModal) easterEggModal.classList.remove("active");
  }

  if (closeEasterEggBtn) closeEasterEggBtn.addEventListener("click", closeEasterEgg);
  if (easterEggModal) {
    easterEggModal.addEventListener("click", (e) => {
      if (e.target === easterEggModal) closeEasterEgg();
    });
  }

  // Easter Egg Trigger 1: Click "InkYard" brand logo 5 times within 3 seconds
  let brandClickCount = 0;
  let brandClickTimer = null;
  if (brandLogo) {
    brandLogo.style.cursor = "pointer";
    brandLogo.addEventListener("click", () => {
      brandClickCount++;
      clearTimeout(brandClickTimer);
      brandClickTimer = setTimeout(() => {
        brandClickCount = 0;
      }, 3000);
      if (brandClickCount >= 5) {
        brandClickCount = 0;
        triggerEasterEgg();
      }
    });
  }

  // Easter Egg Trigger 2: Secret typing sequence "marquant"
  let secretKeyBuffer = "";
  window.addEventListener("keydown", (e) => {
    // Escape key closes modals
    if (e.key === "Escape") {
      closeEasterEgg();
      if (connectModal) connectModal.classList.remove("active");
      if (successModal) successModal.classList.remove("active");
      if (statsModal) statsModal.classList.remove("active");
      if (adModal) adModal.classList.remove("active");
      return;
    }

    // Don't intercept typing when filling in forms
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : "";
    if (tag === "input" || tag === "textarea" || tag === "select") return;

    if (e.key && e.key.length === 1) {
      secretKeyBuffer += e.key.toLowerCase();
      if (secretKeyBuffer.length > 20) {
        secretKeyBuffer = secretKeyBuffer.slice(-20);
      }
      if (secretKeyBuffer.endsWith("marquant")) {
        secretKeyBuffer = "";
        triggerEasterEgg();
      }
    }
  });

  // Confetti particles generator
  function spawnEasterConfetti() {
    const colors = ["#0071e3", "#34c759", "#ff9500", "#ff2d55", "#af52de", "#5856d6", "#ffcc00"];
    for (let i = 0; i < 40; i++) {
      const p = document.createElement("div");
      p.className = "confetti-particle";
      p.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
      p.style.left = `${Math.random() * 95}vw`;
      p.style.top = `${Math.random() * 30 + 10}vh`;
      p.style.animationDuration = `${1.5 + Math.random() * 2}s`;
      p.style.animationDelay = `${Math.random() * 0.4}s`;
      p.style.transform = `rotate(${Math.random() * 360}deg)`;
      document.body.appendChild(p);
      setTimeout(() => p.remove(), 4000);
    }
  }

  function showToast(msg, isError = false) {
    if (!toast) return;
    toast.textContent = msg;
    toast.style.background = isError ? "rgba(255, 59, 48, 0.95)" : "rgba(29, 29, 31, 0.95)";
    toast.classList.add("active");
    setTimeout(() => toast.classList.remove("active"), 3800);
  }
});
