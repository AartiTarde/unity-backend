/**
 * Main Application Module
 * Coordinates all components and handles user interactions
 */

// Application state
const AppState = {
    pdfFile: null,
    fileId: null,
    configId: null,
    excelId: null,
    totalPages: 0,
    extractedData: null,  // Store extracted data for preview
    dataEdited: false  // Track if data was edited
};

// Initialize components
const pdfViewer = new PDFViewer('pdfCanvas');
const gridOverlay = new GridOverlay('overlayCanvas');
const azureVisionIntegration = new AzureVisionIntegration(gridOverlay);

// DOM Elements
const elements = {
    // Upload
    pdfInput: document.getElementById('pdfInput'),
    uploadArea: document.getElementById('uploadArea'),
    fileInfo: document.getElementById('fileInfo'),
    
    // Page settings
    skipPagesStart: document.getElementById('skipPagesStart'),
    skipPagesEnd: document.getElementById('skipPagesEnd'),
    skipHeaderHeight: document.getElementById('skipHeaderHeight'),
    skipFooterHeight: document.getElementById('skipFooterHeight'),
    btnShowSkipZones: document.getElementById('btnShowSkipZones'),
    
    // Grid
    gridRows: document.getElementById('gridRows'),
    gridColumns: document.getElementById('gridColumns'),
    btnDrawGrid: document.getElementById('btnDrawGrid'),
    btnClearGrid: document.getElementById('btnClearGrid'),
    
    // Header Template
    btnHeaderTemplateMode: document.getElementById('btnHeaderTemplateMode'),
    btnApplyHeaderTemplate: document.getElementById('btnApplyHeaderTemplate'),
    headerTemplateStatus: document.getElementById('headerTemplateStatus'),
    
    // Template
    btnTemplateMode: document.getElementById('btnTemplateMode'),
    btnApplyTemplate: document.getElementById('btnApplyTemplate'),
    templateStatus: document.getElementById('templateStatus'),
    
    // Extraction
    btnExtract: document.getElementById('btnExtract'),
    btnDownload: document.getElementById('btnDownload'),
    extractionStatus: document.getElementById('extractionStatus'),
    
    // Preview
    previewSection: document.getElementById('previewSection'),
    extractionSummary: document.getElementById('extractionSummary'),
    btnPreview: document.getElementById('btnPreview'),
    previewModal: document.getElementById('previewModal'),
    btnClosePreview: document.getElementById('btnClosePreview'),
    btnClosePreviewFooter: document.getElementById('btnClosePreviewFooter'),
    btnDownloadFromPreview: document.getElementById('btnDownloadFromPreview'),
    previewStats: document.getElementById('previewStats'),
    previewTableBody: document.getElementById('previewTableBody'),
    
    // Viewer controls
    btnPrevPage: document.getElementById('btnPrevPage'),
    btnNextPage: document.getElementById('btnNextPage'),
    btnZoomIn: document.getElementById('btnZoomIn'),
    btnZoomOut: document.getElementById('btnZoomOut'),
    currentPage: document.getElementById('currentPage'),
    totalPages: document.getElementById('totalPages'),
    zoomLevel: document.getElementById('zoomLevel'),
    
    // Overlay
    loadingOverlay: document.getElementById('loadingOverlay'),
    viewerPlaceholder: document.getElementById('viewerPlaceholder'),
    canvasWrapper: document.getElementById('canvasWrapper'),
    
    // Toast
    toastContainer: document.getElementById('toastContainer')
};

// Event Listeners
function setupEventListeners() {
    // File upload
    elements.pdfInput.addEventListener('change', handleFileSelect);
    elements.uploadArea.addEventListener('dragover', handleDragOver);
    elements.uploadArea.addEventListener('drop', handleFileDrop);
    
    // Skip zones
    elements.btnShowSkipZones.addEventListener('click', handleShowSkipZones);
    
    // Grid
    elements.btnDrawGrid.addEventListener('click', handleDrawGrid);
    elements.btnClearGrid.addEventListener('click', handleClearGrid);
    
    // Header Template
    elements.btnHeaderTemplateMode.addEventListener('click', handleHeaderTemplateMode);
    elements.btnApplyHeaderTemplate.addEventListener('click', handleApplyHeaderTemplate);
    
    // Template
    elements.btnTemplateMode.addEventListener('click', handleTemplateMode);
    elements.btnApplyTemplate.addEventListener('click', handleApplyTemplate);
    
    // Extraction
    elements.btnExtract.addEventListener('click', handleExtract);
    elements.btnDownload.addEventListener('click', handleDownload);
    
    // Preview
    elements.btnPreview.addEventListener('click', handlePreview);
    elements.btnClosePreview.addEventListener('click', closePreviewModal);
    elements.btnClosePreviewFooter.addEventListener('click', closePreviewModal);
    elements.btnDownloadFromPreview.addEventListener('click', saveEditedDataAndRegenerateExcel);
    elements.previewModal.addEventListener('click', (e) => {
        if (e.target === elements.previewModal) closePreviewModal();
    });
    
    // Viewer controls
    elements.btnPrevPage.addEventListener('click', handlePrevPage);
    elements.btnNextPage.addEventListener('click', handleNextPage);
    elements.btnZoomIn.addEventListener('click', handleZoomIn);
    elements.btnZoomOut.addEventListener('click', handleZoomOut);
    
    // Custom events
    window.addEventListener('showToast', (e) => {
        showToast(e.detail.message, e.detail.type);
    });
    
    // Header template box drawn event - enable apply button immediately
    window.addEventListener('headerTemplateBoxDrawn', () => {
        if (gridOverlay.headerTemplateMode && gridOverlay.isHeaderTemplateComplete()) {
            elements.btnApplyHeaderTemplate.disabled = false;
            showToast('Header box drawn! You can now apply the template.', 'success');
        }
    });
}

// File Upload Handlers
async function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        await loadPDFFile(file);
    }
}

function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.uploadArea.classList.add('drag-over');
}

async function handleFileDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    elements.uploadArea.classList.remove('drag-over');
    
    const file = event.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
        await loadPDFFile(file);
    } else {
        showToast('Please drop a PDF file', 'error');
    }
}

async function loadPDFFile(file) {
    try {
        showLoading(true, 'Loading PDF...');
        
        // Load PDF in viewer first
        const result = await pdfViewer.loadPDF(file);
        AppState.pdfFile = file;
        AppState.totalPages = result.totalPages;
        
        // Update UI
        elements.viewerPlaceholder.classList.add('hidden');
        elements.canvasWrapper.classList.remove('hidden');
        elements.currentPage.textContent = '1';
        elements.totalPages.textContent = result.totalPages;
        elements.fileInfo.textContent = `📄 ${file.name} (${result.totalPages} pages)`;
        elements.fileInfo.classList.remove('hidden');
        
        // Enable controls
        elements.btnPrevPage.disabled = false;
        elements.btnNextPage.disabled = false;
        
        // Upload to server (non-blocking, can work offline for preview)
        showLoading(true, 'Uploading to server...');
        try {
            const uploadResult = await API.uploadPDF(file);
            AppState.fileId = uploadResult.fileId;
            console.log('File uploaded successfully:', uploadResult);
            showToast('PDF loaded and uploaded successfully!', 'success');
        } catch (uploadError) {
            console.warn('Server upload failed, but PDF loaded in viewer:', uploadError);
            showToast('PDF loaded in viewer. Upload failed: ' + uploadError.message + ' (You can still adjust grid, but extraction needs server)', 'error');
            // Set fileId to null so extraction knows to fail early
            AppState.fileId = null;
        }
        
        showLoading(false);
        
    } catch (error) {
        console.error('Load PDF error:', error);
        showToast('Failed to load PDF: ' + error.message, 'error');
        showLoading(false);
    }
}

// Skip Zones Handler
function handleShowSkipZones() {
    const headerHeight = parseInt(elements.skipHeaderHeight.value) || 0;
    const footerHeight = parseInt(elements.skipFooterHeight.value) || 0;
    gridOverlay.toggleSkipZones(headerHeight, footerHeight);
}

// Grid Handlers
function handleDrawGrid() {
    const rows = parseInt(elements.gridRows.value) || 9;
    const columns = parseInt(elements.gridColumns.value) || 3;
    
    if (!AppState.pdfFile) {
        showToast('Please upload a PDF first', 'error');
        return;
    }
    
    gridOverlay.drawGrid(rows, columns);
    showToast('Grid drawn! Drag any line to adjust spacing, drag corners to resize, or drag center to move.', 'success');
    
    // Enable template mode button
    elements.btnTemplateMode.disabled = false;
}

function handleClearGrid() {
    gridOverlay.clearGrid();
    elements.btnTemplateMode.disabled = true;
    elements.btnApplyTemplate.disabled = true;
    elements.btnExtract.disabled = true;
    elements.templateStatus.classList.add('hidden');
    showToast('Grid cleared', 'info');
}

// Header Template Handlers
function handleHeaderTemplateMode() {
    const enabled = gridOverlay.enableHeaderTemplateMode();
    if (enabled) {
        elements.btnHeaderTemplateMode.textContent = '✓ Header Template Mode Active';
        elements.btnHeaderTemplateMode.classList.remove('btn-primary');
        elements.btnHeaderTemplateMode.classList.add('btn-success');
        elements.headerTemplateStatus.textContent = 'Use Ctrl+F2 (Booth Center), Ctrl+F3 (Booth Address) to draw boxes on the page header.';
        elements.headerTemplateStatus.classList.remove('hidden');
        elements.headerTemplateStatus.classList.add('info');
        
        // Enable apply button if boxes already exist
        if (gridOverlay.isHeaderTemplateComplete()) {
            elements.btnApplyHeaderTemplate.disabled = false;
        } else {
            elements.btnApplyHeaderTemplate.disabled = true;
        }
        
        showToast('Header template mode enabled. Use Ctrl+F1, F2, F3 to draw header boxes.', 'info');
    }
}

function handleApplyHeaderTemplate() {
    if (!gridOverlay.isHeaderTemplateComplete()) {
        showToast('Please define at least one header box (Ctrl+F1, F2, or F3)', 'error');
        return;
    }
    
    const boxesDefined = [
        gridOverlay.boothCenterBox ? 'Booth Center' : null,
        gridOverlay.boothAddressBox ? 'Booth Address' : null
    ].filter(b => b !== null);
    
    // Mark header template as applied to all pages
    gridOverlay.headerTemplateApplied = true;
    gridOverlay.disableHeaderTemplateMode();
    gridOverlay.redraw();
    elements.btnHeaderTemplateMode.textContent = 'Header Template Defined ✓';
    elements.btnApplyHeaderTemplate.disabled = true;
    elements.headerTemplateStatus.textContent = `✓ Header template applied to ALL PAGES (${boxesDefined.length} boxes: ${boxesDefined.join(', ')})`;
    elements.headerTemplateStatus.classList.remove('info');
    elements.headerTemplateStatus.classList.add('success');
    
    showToast(`Header template applied successfully! ${boxesDefined.length} box(es) will be extracted from the header of ALL pages.`, 'success');
}

// Template Handlers
function handleTemplateMode() {
    const enabled = gridOverlay.enableTemplateMode();
    if (enabled) {
        elements.btnTemplateMode.textContent = '✓ Template Mode Active';
        elements.btnTemplateMode.classList.remove('btn-primary');
        elements.btnTemplateMode.classList.add('btn-success');
        elements.templateStatus.textContent = 'Use Ctrl+1 to Ctrl+9 to draw boxes. Draw on the first cell (top-left).';
        elements.templateStatus.classList.remove('hidden');
        elements.templateStatus.classList.add('info');
        showToast('Template mode enabled. Use Ctrl+1 (Voter ID) to Ctrl+9 (Serial Number) to draw boxes.', 'info');
    }
}

function handleApplyTemplate() {
    if (!gridOverlay.isTemplateComplete()) {
        showToast('Please define at least the Voter ID box (Ctrl+1)', 'error');
        return;
    }
    
    // Count how many boxes are defined
    const boxesDefined = [
        gridOverlay.voterIdBox ? 'Voter ID' : null,
        gridOverlay.nameBox ? 'Name' : null,
        gridOverlay.relativeNameBox ? 'Relative Name' : null,
        gridOverlay.houseNumberBox ? 'House Number' : null,
        gridOverlay.genderBox ? 'Gender' : null,
        gridOverlay.ageBox ? 'Age' : null,
        gridOverlay.assemblyNumberBox ? 'Assembly Number' : null,
        gridOverlay.serialNumberBox ? 'Serial Number' : null,
        gridOverlay.photoBox ? 'Photo' : null
    ].filter(b => b !== null);
    
    gridOverlay.disableTemplateMode();
    gridOverlay.gridResizeDisabled = true; // Disable grid resize after template is applied
    gridOverlay.redraw(); // Redraw to show all boxes on all cells
    elements.btnTemplateMode.textContent = 'Template Defined ✓';
    elements.btnApplyTemplate.disabled = true;
    elements.templateStatus.textContent = `✓ Template applied to all cells (${boxesDefined.length} boxes: ${boxesDefined.join(', ')})`;
    elements.templateStatus.classList.remove('info');
    elements.templateStatus.classList.add('success');
    elements.btnExtract.disabled = false;
    
    showToast(`Template applied successfully! ${boxesDefined.length} box(es) will be extracted from all cells.`, 'success');
}

// Watch for template completion
setInterval(() => {
    if (gridOverlay.templateMode && gridOverlay.isTemplateComplete()) {
        elements.btnApplyTemplate.disabled = false;
    }
    if (gridOverlay.headerTemplateMode && gridOverlay.isHeaderTemplateComplete()) {
        elements.btnApplyHeaderTemplate.disabled = false;
    }
}, 500);

// Extraction Handlers
async function handleExtract() {
    try {
        // Check if PDF file exists
        if (!AppState.pdfFile) {
            showToast('Please upload a PDF file first', 'error');
            return;
        }

        // Check if file was uploaded to server
        if (!AppState.fileId) {
            showToast('PDF upload to server failed. Please ensure the backend server is running and try uploading the PDF again.', 'error');
            return;
        }
        
        const gridConfig = gridOverlay.getGridConfig();
        const templateResult = gridOverlay.getCellTemplate();
        
        if (!gridConfig || !templateResult) {
            showToast('Please complete grid and template configuration first', 'error');
            return;
        }
        
        showLoading(true, 'Configuring extraction...');
        
        // Get PDF scale for coordinate conversion
        const pdfScale = gridOverlay.pdfScale || 1.5;
        
        // Configure extraction
        // IMPORTANT: skipHeaderHeight and skipFooterHeight are in CANVAS coordinates,
        // so we need to convert them to PDF coordinates too!
        const config = {
            fileId: AppState.fileId,
            skipPagesStart: parseInt(elements.skipPagesStart.value) || 0,
            skipPagesEnd: parseInt(elements.skipPagesEnd.value) || 0,
            skipHeaderHeight: (parseInt(elements.skipHeaderHeight.value) || 0) / pdfScale,
            skipFooterHeight: (parseInt(elements.skipFooterHeight.value) || 0) / pdfScale,
            grid: gridConfig,
            cellTemplate: templateResult.cellTemplate || {},
            headerTemplate: templateResult.headerTemplate || {}
        };
        
        console.log('Extraction Configuration (converted to PDF coordinates):', config);
        console.log(`PDF Scale used for conversion: ${pdfScale}`);
        
        const configResult = await API.configureExtraction(config);
        AppState.configId = configResult.configId;
        
        showLoading(true, 'Extracting data... This may take a few minutes.');
        
        // Start extraction
        const extractResult = await API.extractGrid(AppState.configId);
        AppState.excelId = extractResult.excelId;
        AppState.extractedData = extractResult.extractedData || [];  // Store extracted data
        AppState.extractionStats = extractResult.stats || {};  // Store extraction statistics
        
        console.log('Extraction completed. Records:', extractResult.recordsExtracted);
        console.log('Extracted data available:', extractResult.extractedData ? extractResult.extractedData.length : 0, 'records');
        console.log('Excel ID:', AppState.excelId);
        console.log('Extraction stats:', AppState.extractionStats);
        
        showLoading(false);
        
        // Get stats from result
        const stats = extractResult.stats || {};
        const extractionTime = stats.extraction_time_seconds || 0;
        const cellsSkipped = stats.cells_skipped || 0;
        const accuracyRate = stats.accuracy_rate || 0;
        const apiCallsUsed = stats.api_calls_used || 0;
        
        // Format time
        const timeFormatted = extractionTime > 60 
            ? `${Math.floor(extractionTime / 60)}m ${Math.round(extractionTime % 60)}s`
            : `${Math.round(extractionTime)}s`;
        
        // Update UI
        elements.extractionStatus.textContent = `✓ Extracted ${extractResult.recordsExtracted} records successfully!`;
        elements.extractionStatus.classList.remove('hidden');
        elements.extractionStatus.classList.add('success');
        
        // Show preview section with stats
        let summaryHtml = `
            <div style="margin-bottom: 12px;">
                <strong style="font-size: 18px; color: #10b981;">${extractResult.recordsExtracted}</strong> records extracted successfully!
            </div>
        `;
        
        if (extractionTime > 0 || cellsSkipped > 0 || accuracyRate > 0 || apiCallsUsed > 0) {
            summaryHtml += `<div style="margin-top: 12px; padding: 12px; background: #f3f4f6; border-radius: 8px; font-size: 13px;">`;
            
            if (extractionTime > 0) {
                summaryHtml += `
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span>⏱️</span>
                        <span><strong>Time:</strong> ${timeFormatted}</span>
                    </div>
                `;
            }
            
            if (accuracyRate > 0) {
                const accuracyColor = accuracyRate >= 95 ? '#10b981' : accuracyRate >= 85 ? '#f59e0b' : '#ef4444';
                summaryHtml += `
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span>🎯</span>
                        <span><strong>Accuracy Rate:</strong> <span style="color: ${accuracyColor}; font-weight: bold;">${accuracyRate.toFixed(1)}%</span></span>
                    </div>
                `;
            }
            
            if (apiCallsUsed > 0) {
                summaryHtml += `
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span>📡</span>
                        <span><strong>API Calls Used:</strong> <span style="color: ${apiCallsUsed > 10 ? '#ef4444' : '#f59e0b'}; font-weight: bold;">${apiCallsUsed}</span></span>
                    </div>
                `;
            } else {
                summaryHtml += `
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span>✓</span>
                        <span style="color: #10b981;"><strong>No API calls needed</strong> (using PDF text layer)</span>
                    </div>
                `;
            }
            
            if (cellsSkipped > 0) {
                summaryHtml += `
                    <div style="display: flex; align-items: center; gap: 8px; margin-top: 8px; padding-top: 8px; border-top: 1px solid #e5e7eb;">
                        <span>⊘</span>
                        <span style="color: #f59e0b;"><strong>Skipped:</strong> ${cellsSkipped} cells (no voter ID found)</span>
                    </div>
                `;
            }
            
            summaryHtml += `</div>`;
        }
        
        summaryHtml += `<div style="margin-top: 12px; font-size: 13px; color: #6b7280;">Click "Preview Data" to see results before downloading.</div>`;
        
        // Show preview section with data
        console.log('Showing preview section. Hidden class:', elements.previewSection.classList.contains('hidden'));
        elements.previewSection.classList.remove('hidden');
        console.log('After removal. Hidden class:', elements.previewSection.classList.contains('hidden'));
        elements.extractionSummary.innerHTML = summaryHtml;
        elements.btnDownload.disabled = true; // Disable download since Excel is not created
        elements.btnPreview.disabled = false;  // Ensure preview button is enabled
        
        console.log('Preview section shown. Data ready:', AppState.extractedData ? AppState.extractedData.length : 0, 'records');
        
        // Show toast with stats
        let toastMsg = `Extraction complete! ${extractResult.recordsExtracted} records extracted.`;
        if (extractionTime > 0) toastMsg += ` Time: ${timeFormatted}`;
        showToast(toastMsg, 'success');
        
        // Clear drawn boxes after extraction
        gridOverlay.voterIdBox = null;
        gridOverlay.photoBox = null;
        gridOverlay.nameBox = null;
        gridOverlay.relativeNameBox = null;
        gridOverlay.houseNumberBox = null;
        gridOverlay.genderBox = null;
        gridOverlay.ageBox = null;
        gridOverlay.assemblyNumberBox = null;
        gridOverlay.serialNumberBox = null;
        gridOverlay.boothCenterBox = null;
        gridOverlay.boothAddressBox = null;
        gridOverlay.headerTemplateApplied = false;
        
        // Enable header template mode for drawing Booth Center and Booth Address
        gridOverlay.enableHeaderTemplateMode();
        elements.btnHeaderTemplateMode.textContent = '✓ Header Template Mode Active';
        elements.btnHeaderTemplateMode.classList.remove('btn-primary');
        elements.btnHeaderTemplateMode.classList.add('btn-success');
        elements.headerTemplateStatus.textContent = 'Use Ctrl+F2 (Booth Center), Ctrl+F3 (Booth Address) to draw boxes on the page header.';
        elements.headerTemplateStatus.classList.remove('hidden');
        elements.headerTemplateStatus.classList.add('info');
        elements.btnApplyHeaderTemplate.disabled = true;
        
        gridOverlay.redraw();
        showToast('Boxes cleared. You can now draw Booth Center (Ctrl+F2) and Booth Address (Ctrl+F3) boxes.', 'info');
        
    } catch (error) {
        console.error('Extraction error:', error);
        showLoading(false);
        if (error.message.includes('Failed to fetch') || error.message.includes('Cannot connect')) {
            showToast('Cannot connect to server. Please ensure both Node.js and Python servers are running (START_SERVERS.bat)', 'error');
        } else {
            showToast('Extraction failed: ' + error.message, 'error');
        }
    }
}

function handleDownload() {
    if (!AppState.excelId) {
        showToast('No file to download', 'error');
        return;
    }
    
    API.downloadExcel(AppState.excelId);
    showToast('Downloading Excel file...', 'success');
}

// Viewer Control Handlers
async function handlePrevPage() {
    await pdfViewer.prevPage();
    updatePageDisplay();
    gridOverlay.redraw();
}

async function handleNextPage() {
    await pdfViewer.nextPage();
    updatePageDisplay();
    gridOverlay.redraw();
}

async function handleZoomIn() {
    await pdfViewer.zoomIn();
    updateZoomDisplay();
    gridOverlay.redraw();
}

async function handleZoomOut() {
    await pdfViewer.zoomOut();
    updateZoomDisplay();
    gridOverlay.redraw();
}

function updatePageDisplay() {
    elements.currentPage.textContent = pdfViewer.currentPage;
}

function updateZoomDisplay() {
    elements.zoomLevel.textContent = pdfViewer.getZoomLevel() + '%';
}

// UI Helpers
function showLoading(show, message = 'Processing...') {
    if (show) {
        elements.loadingOverlay.classList.remove('hidden');
        const loadingText = elements.loadingOverlay.querySelector('.loading-text');
        if (loadingText) {
            loadingText.textContent = message;
        }
    } else {
        elements.loadingOverlay.classList.add('hidden');
    }
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        error: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>',
        info: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
    };
    
    toast.innerHTML = `
        ${icons[type] || icons.info}
        <div class="toast-message">${message}</div>
    `;
    
    elements.toastContainer.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function getConfidenceClass(confidence) {
    if (confidence >= 0.8) return 'confidence-high';
    if (confidence >= 0.5) return 'confidence-medium';
    return 'confidence-low';
}

// Preview Modal Handlers
function handlePreview() {
    console.log('Preview button clicked. Data available:', AppState.extractedData ? AppState.extractedData.length : 0);
    
    if (!AppState.extractedData || AppState.extractedData.length === 0) {
        console.error('No data to preview');
        showToast('No data to preview', 'error');
        return;
    }
    
    console.log('Opening preview modal...');
    // Show modal
    elements.previewModal.classList.remove('hidden');
    
    // Reset modal header
    const modalHeader = elements.previewModal.querySelector('.modal-header h2');
    if (modalHeader) {
        if (AppState.dataEdited) {
            modalHeader.innerHTML = '📊 Extracted Data Preview <span style="color: var(--color-success); font-size: 0.875rem; font-weight: normal;">(Edited)</span>';
        } else {
            modalHeader.innerHTML = '📊 Extracted Data Preview';
        }
    }
    
    // Populate stats
    const totalRecords = AppState.extractedData.length;
    const withVoterIds = AppState.extractedData.filter(r => r.voterID && r.voterID.trim()).length;
    const withPhotos = AppState.extractedData.filter(r => r.image_base64 && r.image_base64.trim()).length;
    
    // Get accuracy rate and API call stats from extraction result (stored in AppState)
    // These should be passed from the extraction result
    const extractionStats = AppState.extractionStats || {};
    const accuracyRate = extractionStats.accuracy_rate || 0;
    const apiCallsUsed = extractionStats.api_calls_used || 0;
    const pdfTextLayerFields = extractionStats.pdf_text_layer_fields || 0;
    const ocrFields = extractionStats.ocr_fields || 0;
    
    // Calculate accuracy color
    const accuracyColor = accuracyRate >= 95 ? '#10b981' : accuracyRate >= 85 ? '#f59e0b' : '#ef4444';
    
    elements.previewStats.innerHTML = `
        <div class="stat-item">
            <span class="stat-value">${totalRecords}</span>
            <span class="stat-label">Total Records</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${withVoterIds}</span>
            <span class="stat-label">Voter IDs Found</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${withPhotos}</span>
            <span class="stat-label">Photos Extracted</span>
        </div>
        <div class="stat-item" style="border-top: 2px solid #e5e7eb; padding-top: 12px; margin-top: 8px;">
            <span class="stat-value" style="color: ${accuracyColor}; font-size: 24px; font-weight: bold;">${accuracyRate.toFixed(1)}%</span>
            <span class="stat-label">Accuracy Rate</span>
        </div>
        <div class="stat-item">
            <span class="stat-value" style="color: ${apiCallsUsed > 0 ? '#f59e0b' : '#10b981'};">
                ${apiCallsUsed}
            </span>
            <span class="stat-label">API Calls Used</span>
        </div>
        <div class="stat-item" style="font-size: 11px; color: #6b7280; padding-top: 8px; border-top: 1px solid #e5e7eb; margin-top: 8px;">
            <div style="margin-bottom: 4px;">
                <span style="color: #10b981;">✓ PDF Text Layer:</span> ${pdfTextLayerFields} fields (99% accuracy)
            </div>
            <div style="margin-bottom: 4px;">
                <span style="color: #3b82f6;">OCR Fallback:</span> ${ocrFields} fields (85% accuracy)
            </div>
            ${apiCallsUsed > 0 ? `<div><span style="color: #f59e0b;">API Fallback:</span> ${apiCallsUsed} calls (95% accuracy)</div>` : ''}
        </div>
    `;
    
    // Populate table with editable voter ID fields
    elements.previewTableBody.innerHTML = AppState.extractedData.map((record, index) => {
        const confidence = record.metadata?.voter_id_confidence || 0;
        const confidenceClass = getConfidenceClass(confidence);
        const confidencePercent = (confidence * 100).toFixed(0);
        const isLowConfidence = confidence < 0.8;  // Mark low confidence
        const voterIdValue = (record.voterID || '').replace(/"/g, '&quot;');
        
        // Create editable input - all voter IDs are editable, but low confidence ones are highlighted
        const voterIdHtml = isLowConfidence 
            ? `<input type="text" 
                     class="voter-id-input editable-input" 
                     value="${voterIdValue}" 
                     data-index="${index}"
                     placeholder="Enter voter ID"
                     title="⚠️ Low accuracy detected (${confidencePercent}%) - please verify and edit if needed">`
            : `<input type="text" 
                     class="voter-id-input" 
                     value="${voterIdValue}" 
                     data-index="${index}"
                     placeholder="Enter voter ID"
                     title="Click to edit voter ID">`;
        
        return `
            <tr data-index="${index}">
                <td>${index + 1}</td>
                <td>${record.page || '-'}</td>
                <td>${record.row || '-'}</td>
                <td>${record.column || '-'}</td>
                <td class="voter-id-cell">
                    ${voterIdHtml}
                </td>
                <td>${record.name || '-'}</td>
                <td>${record.nameEnglish || '-'}</td>
                <td>${record.relativeName || '-'}</td>
                <td>${record.relativeNameEnglish || '-'}</td>
                <td>${record.relativeType || '-'}</td>
                <td>${record.houseNumber || '-'}</td>
                <td>${record.gender || '-'}</td>
                <td>${record.age || '-'}</td>
                <td>${record.assemblyNumber || '-'}</td>
                <td>${record.serialNumber || '-'}</td>
                <td>${record.boothCenter || '-'}</td>
                <td>${record.boothAddress || '-'}</td>
                <td class="photo-cell">
                    ${record.image_base64 
                        ? `<img src="data:image/jpeg;base64,${record.image_base64}" 
                             alt="Voter Photo" 
                             class="preview-photo" 
                             title="Click to zoom">`
                        : '<span class="no-data">No Photo</span>'}
                </td>
                <td>
                    <span class="confidence-badge ${confidenceClass}">
                        ${confidencePercent}%
                    </span>
                </td>
            </tr>
        `;
    }).join('');
    
    // Add event listeners for voter ID editing
    setupVoterIdEditing();
    
    showToast(`Previewing ${totalRecords} records. You can edit voter IDs directly in the table.`, 'info');
}

function closePreviewModal() {
    elements.previewModal.classList.add('hidden');
}

// Update preview modal header to show edit status
function updatePreviewModalHeader() {
    const modalHeader = elements.previewModal.querySelector('.modal-header h2');
    if (modalHeader) {
        if (AppState.dataEdited) {
            if (!modalHeader.textContent.includes('(Edited)')) {
                modalHeader.innerHTML = '📊 Extracted Data Preview <span style="color: var(--color-success); font-size: 0.875rem; font-weight: normal;">(Edited)</span>';
            }
        }
    }
}

// Setup voter ID editing functionality
function setupVoterIdEditing() {
    const voterIdInputs = elements.previewTableBody.querySelectorAll('.voter-id-input');
    
    voterIdInputs.forEach(input => {
        // Save on blur (when user clicks away)
        input.addEventListener('blur', (e) => {
            const index = parseInt(e.target.dataset.index);
            const newValue = e.target.value.trim();
            
            if (index >= 0 && index < AppState.extractedData.length) {
                const oldValue = AppState.extractedData[index].voterID || '';
                if (newValue !== oldValue) {
                    AppState.extractedData[index].voterID = newValue;
                    AppState.dataEdited = true;
                    
                    // Update visual indicator
                    e.target.classList.add('edited');
                    
                    // Update modal header to show data has been edited
                    updatePreviewModalHeader();
                    
                    showToast(`Voter ID updated for record ${index + 1}`, 'success');
                }
            }
        });
        
        // Save on Enter key
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.target.blur();
            }
        });
        
        // Highlight editable fields on focus
        input.addEventListener('focus', (e) => {
            e.target.classList.add('editing');
        });
        
        input.addEventListener('blur', (e) => {
            e.target.classList.remove('editing');
        });
    });
}

// Save edited data and regenerate Excel
async function saveEditedDataAndRegenerateExcel() {
    if (!AppState.dataEdited) {
        // No changes made, just download existing Excel
        handleDownload();
        return;
    }
    
    try {
        showLoading(true, 'Regenerating Excel with updated data...');
        
        // Call API to regenerate Excel with updated data
        const result = await API.updateExcelData(AppState.excelId, AppState.extractedData);
        
        if (result.success) {
            AppState.excelId = result.excelId;  // Update to new Excel ID
            AppState.dataEdited = false;  // Reset edit flag
            
            // Download the updated Excel
            handleDownload();
            showToast('Excel regenerated with updated data!', 'success');
        } else {
            showToast('Failed to update Excel: ' + (result.error || 'Unknown error'), 'error');
        }
        
        showLoading(false);
    } catch (error) {
        console.error('Error regenerating Excel:', error);
        showLoading(false);
        showToast('Failed to regenerate Excel: ' + error.message, 'error');
    }
}

// Check server health on load
async function checkServerHealth() {
    const isHealthy = await API.checkHealth();
    if (!isHealthy) {
        showToast('Warning: Cannot connect to backend server. Please ensure it is running.', 'error');
    }
}

// Initialize application
function init() {
    console.log('Initializing Grid-Based PDF Voter Data Extraction Tool');
    setupEventListeners();
    checkServerHealth();
    
    // Initial state
    elements.canvasWrapper.classList.add('hidden');
    
    console.log('Application initialized successfully');
}

// Start application when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}


