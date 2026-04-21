
function setActiveTab(tab) {
  tabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });

  // Hide all sections first
  const allSections = [letterSection, itinerarySection, bookingSection,
    outputsSection, translateSection, classifierSection, pdfSection, editpdfSection];
  const aisplitterSection = document.getElementById("aisplitterSection");
  const precheckSection = document.getElementById("precheckSection");
  const insSection = document.getElementById("insuranceSection");
  const compressSection = document.getElementById("compressSection");
  if (aisplitterSection) allSections.push(aisplitterSection);
  if (precheckSection) allSections.push(precheckSection);
  if (insSection) allSections.push(insSection);
  if (compressSection) allSections.push(compressSection);
  allSections.forEach((s) => { if (s) s.classList.add("hidden"); });

  if (tab === "letter") {
    letterSection.classList.remove("hidden");
    // Init V3 letter gen UI
    if (typeof initLetterGen === 'function') initLetterGen();
  } else if (tab === "itinerary") {
    itinerarySection.classList.remove("hidden");
    // Keep itinerary form clean by default.
    // Users populate this section via extraction or manual input.
  } else if (tab === "booking") {
    bookingSection.classList.remove("hidden");
    setBookingPart("flight");
    loadLatestBooking();
    loadLatestTripInfo();
    loadFilteredFiles();
  } else if (tab === "outputs") {
    outputsSection.classList.remove("hidden");
    loadLatestItinerary().then(syncCombinedPreviews);
    loadLatestBooking().then(syncCombinedPreviews);
    syncCombinedPreviews();
  } else if (tab === "translate") {
    if (translateSection) translateSection.classList.remove("hidden");
    initTranslationSection();
  } else if (tab === "classifier") {
    classifierSection.classList.remove("hidden");
    loadClassifierFiles();
  } else if (tab === "pdf") {
    pdfSection.classList.remove("hidden");
    loadPdfFiles();
  } else if (tab === "aisplitter") {
    if (aisplitterSection) aisplitterSection.classList.remove("hidden");
    loadSplitterFileList();
  } else if (tab === "precheck") {
    if (precheckSection) precheckSection.classList.remove("hidden");
  } else if (tab === "editpdf") {
    if (editpdfSection) editpdfSection.classList.remove("hidden");
    initEditPdfUI();
  } else if (tab === "insurance") {
    if (insSection) insSection.classList.remove("hidden");
  } else if (tab === "compress") {
    if (compressSection) compressSection.classList.remove("hidden");
    if (typeof initCompressToolsSection === "function") initCompressToolsSection();
  }
}

