

function setActiveTab(tab) {
  tabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });

  // Hide all sections first
  const allSections = [letterSection, itinerarySection, bookingSection,
    outputsSection, translateSection, classifierSection, pdfSection, editpdfSection];
  const aisplitterSection = document.getElementById("aisplitterSection");
  const precheckSection = document.getElementById("precheckSection");
  if (aisplitterSection) allSections.push(aisplitterSection);
  if (precheckSection) allSections.push(precheckSection);
  allSections.forEach((s) => { if (s) s.classList.add("hidden"); });

  if (tab === "letter") {
    letterSection.classList.remove("hidden");
  } else if (tab === "itinerary") {
    itinerarySection.classList.remove("hidden");
    loadLatestItinerary();
    loadItineraryContext();
  } else if (tab === "booking") {
    bookingSection.classList.remove("hidden");
    setBookingPart("hotel");
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
  }
}

async function runAll() {
  for (const step of LETTER_STEP_ORDER) {
    await runStep(step, true);
  }
}

