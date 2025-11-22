/**
 * Grid Overlay Module
 * Handles grid drawing, cell selection, and template definition
 */

class GridOverlay {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.context = this.canvas.getContext('2d');
        
        // Grid state
        this.grid = null;
        this.isDrawing = false;
        this.isDragging = false;
        this.isResizing = false;
        this.isDraggingLine = false;
        this.resizeHandle = null; // 'topLeft', 'topRight', 'bottomLeft', 'bottomRight'
        this.draggedLine = null; // {type: 'row'|'col', index: number}
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.gridStartX = 0;
        this.gridStartY = 0;
        this.gridStartWidth = 0;
        this.gridStartHeight = 0;
        
        // Custom line positions (for non-uniform grids)
        this.customRowPositions = []; // Array of y positions
        this.customColPositions = []; // Array of x positions
        
        // Template state
        this.templateMode = false;
        this.headerTemplateMode = false;
        this.templateType = null; // 'voterID', 'photo', 'name', 'relativeName', 'houseNumber', 'gender', 'age', 'assemblyNumber', 'serialNumber'
        this.voterIdBox = null;
        this.photoBox = null;
        this.nameBox = null;
        this.relativeNameBox = null;
        this.houseNumberBox = null;
        this.genderBox = null;
        this.ageBox = null;
        this.assemblyNumberBox = null;
        this.serialNumberBox = null;
        
        // Header template state (page-level fields)
        this.boothCenterBox = null;
        this.boothAddressBox = null;
        this.headerTemplateApplied = false; // Track if header template is applied to all pages
        
        // Grid resize state
        this.gridResizeDisabled = false; // Disable resize handles after template is applied
        
        // Drawing state
        this.drawStart = null;
        this.currentRect = null;
        
        // Skip zones
        this.showSkipZones = false;
        this.headerHeight = 0;
        this.footerHeight = 0;
        
        // PDF scale (CRITICAL: must match pdfViewer scale for coordinate conversion)
        this.pdfScale = 1.5;  // Default scale from PDFViewer
        
        // Bind event listeners
        this.setupEventListeners();
    }
    
    /**
     * Set PDF scale for coordinate conversion
     * Must be called when PDF scale changes
     */
    setPDFScale(scale) {
        this.pdfScale = scale;
        console.log(`Grid overlay scale updated to: ${scale}`);
    }

    setupEventListeners() {
        this.canvas.addEventListener('mousedown', this.handleMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.handleMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.handleMouseUp.bind(this));
        
        // Listen for PDF page rendered events
        window.addEventListener('pdfPageRendered', this.handlePDFPageRendered.bind(this));
        
        // Listen for keyboard events
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
    }

    handlePDFPageRendered(event) {
        const { width, height, scale } = event.detail;
        this.canvas.width = width;
        this.canvas.height = height;
        
        // Match the PDF canvas display size exactly
        const pdfCanvas = document.getElementById('pdfCanvas');
        if (pdfCanvas) {
            this.canvas.style.width = pdfCanvas.style.width || width + 'px';
            this.canvas.style.height = pdfCanvas.style.height || height + 'px';
            this.canvas.style.display = 'block';
        }
        
        // CRITICAL: Update PDF scale for coordinate conversion
        if (scale !== undefined) {
            this.setPDFScale(scale);
        }
        
        this.redraw();
    }

    handleMouseDown(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        if (this.headerTemplateMode) {
            // Header template mode - draw boxes anywhere on the page (absolute coordinates)
            // Only allow drawing if a template type is selected
            if (this.templateType && (this.templateType === 'boothCenter' || this.templateType === 'boothAddress')) {
                this.isDrawing = true;
                this.drawStart = { x, y };
                this.canvas.style.cursor = 'crosshair';
            } else {
                this.showToast('Please select a field first: Ctrl+F2 (Booth Center), or Ctrl+F3 (Booth Address)', 'warning');
            }
        } else if (this.templateMode && this.grid) {
            // Cell template mode - draw sub-regions in first cell
            this.isDrawing = true;
            this.drawStart = { x, y };
        } else if (this.grid && !this.templateMode && !this.headerTemplateMode && !this.gridResizeDisabled) {
            // Check if clicking on resize handle
            const handle = this.getResizeHandle(x, y);
            if (handle) {
                this.isResizing = true;
                this.resizeHandle = handle;
                this.dragStartX = x;
                this.dragStartY = y;
                this.gridStartX = this.grid.x;
                this.gridStartY = this.grid.y;
                this.gridStartWidth = this.grid.width;
                this.gridStartHeight = this.grid.height;
                return;
            }
            
            // Check if clicking on a grid line
            const line = this.getGridLineAtPoint(x, y);
            if (line) {
                this.isDraggingLine = true;
                this.draggedLine = line;
                this.dragStartX = x;
                this.dragStartY = y;
                return;
            }
            
            // Check if clicking on grid for dragging
            if (this.isPointInGrid(x, y)) {
                this.isDragging = true;
                this.dragStartX = x - this.grid.x;
                this.dragStartY = y - this.grid.y;
            }
        }
    }

    handleMouseMove(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        // Update cursor in header template mode when field is selected
        if (this.headerTemplateMode && !this.isDrawing) {
            if (this.templateType && (this.templateType === 'boothCenter' || this.templateType === 'boothAddress')) {
                this.canvas.style.cursor = 'crosshair';
            } else {
                this.canvas.style.cursor = 'default';
            }
        }

        if (this.isDrawing && this.drawStart) {
            // Drawing template boxes
            this.currentRect = {
                x: Math.min(this.drawStart.x, x),
                y: Math.min(this.drawStart.y, y),
                width: Math.abs(x - this.drawStart.x),
                height: Math.abs(y - this.drawStart.y)
            };
            this.redraw();
        } else if (this.isDraggingLine && this.draggedLine) {
            // Dragging individual grid line
            if (this.draggedLine.type === 'row') {
                const newY = y;
                // Constrain within grid bounds
                if (newY > this.grid.y && newY < this.grid.y + this.grid.height) {
                    this.customRowPositions[this.draggedLine.index] = newY;
                }
            } else if (this.draggedLine.type === 'col') {
                const newX = x;
                // Constrain within grid bounds
                if (newX > this.grid.x && newX < this.grid.x + this.grid.width) {
                    this.customColPositions[this.draggedLine.index] = newX;
                }
            }
            this.redraw();
        } else if (this.isResizing && this.grid) {
            // Resizing grid from corner
            const deltaX = x - this.dragStartX;
            const deltaY = y - this.dragStartY;

            switch (this.resizeHandle) {
                case 'topLeft':
                    this.grid.x = this.gridStartX + deltaX;
                    this.grid.y = this.gridStartY + deltaY;
                    this.grid.width = this.gridStartWidth - deltaX;
                    this.grid.height = this.gridStartHeight - deltaY;
                    break;
                case 'topRight':
                    this.grid.y = this.gridStartY + deltaY;
                    this.grid.width = this.gridStartWidth + deltaX;
                    this.grid.height = this.gridStartHeight - deltaY;
                    break;
                case 'bottomLeft':
                    this.grid.x = this.gridStartX + deltaX;
                    this.grid.width = this.gridStartWidth - deltaX;
                    this.grid.height = this.gridStartHeight + deltaY;
                    break;
                case 'bottomRight':
                    this.grid.width = this.gridStartWidth + deltaX;
                    this.grid.height = this.gridStartHeight + deltaY;
                    break;
            }

            // Ensure minimum size
            if (this.grid.width < 100) this.grid.width = 100;
            if (this.grid.height < 100) this.grid.height = 100;

            // Reset custom positions when resizing
            this.initializeCustomPositions();
            this.redraw();
        } else if (this.isDragging && this.grid) {
            // Dragging grid
            this.grid.x = x - this.dragStartX;
            this.grid.y = y - this.dragStartY;
            this.redraw();
        } else if (this.grid && !this.templateMode && !this.gridResizeDisabled) {
            // Update cursor based on hover position
            const handle = this.getResizeHandle(x, y);
            if (handle) {
                this.updateCursor(handle);
            } else {
                const line = this.getGridLineAtPoint(x, y);
                if (line) {
                    this.canvas.style.cursor = line.type === 'row' ? 'ns-resize' : 'ew-resize';
                } else if (this.isPointInGrid(x, y)) {
                    this.canvas.style.cursor = 'move';
                } else {
                    this.canvas.style.cursor = 'default';
                }
            }
        }
    }

    handleMouseUp(event) {
        if (this.isDrawing && this.currentRect) {
            const box = { ...this.currentRect };
            
            if (this.headerTemplateMode) {
                // Header template mode: boxes are absolute coordinates (relative to page top)
                // No conversion needed - use as-is
                if (this.templateType === 'boothCenter') {
                    this.boothCenterBox = box;
                    console.log('Booth Center box defined (header):', this.boothCenterBox);
                } else if (this.templateType === 'boothAddress') {
                    this.boothAddressBox = box;
                    console.log('Booth Address box defined (header):', this.boothAddressBox);
                }
                // Enable apply button if at least one box is defined
                if (this.isHeaderTemplateComplete()) {
                    window.dispatchEvent(new CustomEvent('headerTemplateBoxDrawn'));
                }
            } else if (this.templateMode) {
                // Cell template mode: boxes are relative to first cell
                const firstCell = this.getFirstCell();
                // Convert to relative coordinates (relative to first cell)
                box.x -= firstCell.x;
                box.y -= firstCell.y;
                
                if (this.templateType === 'voterID') {
                    this.voterIdBox = box;
                    console.log('Voter ID box defined:', this.voterIdBox);
                } else if (this.templateType === 'photo') {
                    this.photoBox = box;
                    console.log('Photo box defined:', this.photoBox);
                } else if (this.templateType === 'name') {
                    this.nameBox = box;
                    console.log('Name box defined:', this.nameBox);
                } else if (this.templateType === 'relativeName') {
                    this.relativeNameBox = box;
                    console.log('Relative Name box defined:', this.relativeNameBox);
                } else if (this.templateType === 'houseNumber') {
                    this.houseNumberBox = box;
                    console.log('House Number box defined:', this.houseNumberBox);
                } else if (this.templateType === 'gender') {
                    this.genderBox = box;
                    console.log('Gender box defined:', this.genderBox);
                } else if (this.templateType === 'age') {
                    this.ageBox = box;
                    console.log('Age box defined:', this.ageBox);
                } else if (this.templateType === 'assemblyNumber') {
                    this.assemblyNumberBox = box;
                    console.log('Assembly Number box defined:', this.assemblyNumberBox);
                } else if (this.templateType === 'serialNumber') {
                    this.serialNumberBox = box;
                    console.log('Serial Number box defined:', this.serialNumberBox);
                }
            }
            this.currentRect = null;
        }

        this.isDrawing = false;
        this.isDragging = false;
        this.isResizing = false;
        this.isDraggingLine = false;
        this.resizeHandle = null;
        this.draggedLine = null;
        this.canvas.style.cursor = 'default';
        this.redraw();
    }

    handleKeyDown(event) {
        if (this.headerTemplateMode) {
            // Header template mode - only F2, F3 work here
            if (event.ctrlKey || event.metaKey) {
                if (event.key === 'F2') {
                    this.templateType = 'boothCenter';
                    this.canvas.style.cursor = 'crosshair';
                    this.showToast('Booth Center selected - Click and drag to draw box', 'info');
                    event.preventDefault();
                    this.redraw();
                } else if (event.key === 'F3') {
                    this.templateType = 'boothAddress';
                    this.canvas.style.cursor = 'crosshair';
                    this.showToast('Booth Address selected - Click and drag to draw box', 'info');
                    event.preventDefault();
                    this.redraw();
                }
            }
        } else if (this.templateMode) {
            // Cell template mode - only Ctrl+1 to Ctrl+9 work here
            if (event.ctrlKey || event.metaKey) {
                const key = event.key;
                if (key === '1') {
                    this.templateType = 'voterID';
                    this.showToast('Draw Voter ID box (Ctrl+1)', 'info');
                    event.preventDefault();
                } else if (key === '2') {
                    this.templateType = 'name';
                    this.showToast('Draw Name box (Ctrl+2)', 'info');
                    event.preventDefault();
                } else if (key === '3') {
                    this.templateType = 'relativeName';
                    this.showToast('Draw Relative Name box (Ctrl+3)', 'info');
                    event.preventDefault();
                } else if (key === '4') {
                    this.templateType = 'houseNumber';
                    this.showToast('Draw House Number box (Ctrl+4)', 'info');
                    event.preventDefault();
                } else if (key === '5') {
                    this.templateType = 'gender';
                    this.showToast('Draw Gender box (Ctrl+5)', 'info');
                    event.preventDefault();
                } else if (key === '6') {
                    this.templateType = 'age';
                    this.showToast('Draw Age box (Ctrl+6)', 'info');
                    event.preventDefault();
                } else if (key === '7') {
                    this.templateType = 'assemblyNumber';
                    this.showToast('Draw Assembly Number box (Ctrl+7)', 'info');
                    event.preventDefault();
                } else if (key === '8') {
                    this.templateType = 'photo';
                    this.showToast('Draw Photo box (Ctrl+8)', 'info');
                    event.preventDefault();
                } else if (key === '9') {
                    this.templateType = 'serialNumber';
                    this.showToast('Draw Serial Number box (Ctrl+9)', 'info');
                    event.preventDefault();
                }
            }
            // Legacy support for V and I keys
            else if (event.key === 'v' || event.key === 'V') {
                this.templateType = 'voterID';
                this.showToast('Draw Voter ID box (or use Ctrl+1)', 'info');
            } else if (event.key === 'i' || event.key === 'I') {
                this.templateType = 'photo';
                this.showToast('Draw Photo box (or use Ctrl+8)', 'info');
            }
        } else if (this.grid && !this.templateMode && !this.headerTemplateMode) {
            // Grid adjustment with arrow keys
            const step = event.shiftKey ? 10 : 1; // Hold Shift for larger steps
            let changed = false;
            
            switch(event.key) {
                case 'ArrowUp':
                    this.grid.y -= step;
                    changed = true;
                    break;
                case 'ArrowDown':
                    this.grid.y += step;
                    changed = true;
                    break;
                case 'ArrowLeft':
                    this.grid.x -= step;
                    changed = true;
                    break;
                case 'ArrowRight':
                    this.grid.x += step;
                    changed = true;
                    break;
                case '+':
                case '=':
                    // Increase grid size
                    this.grid.width += step * 2;
                    this.grid.height += step * 2;
                    changed = true;
                    break;
                case '-':
                case '_':
                    // Decrease grid size
                    this.grid.width -= step * 2;
                    this.grid.height -= step * 2;
                    changed = true;
                    break;
            }
            
            if (changed) {
                event.preventDefault();
                this.redraw();
            }
        }
    }

    /**
     * Draw grid on canvas
     */
    drawGrid(rows, columns, x = null, y = null, width = null, height = null) {
        if (!this.canvas.width || !this.canvas.height) {
            console.error('Canvas not initialized');
            return;
        }

        // Auto-calculate dimensions if not provided
        // Better defaults for voter card documents
        if (x === null) {
            x = Math.round(this.canvas.width * 0.05); // 5% margin from left
        }
        if (y === null) {
            y = Math.round(this.canvas.height * 0.10); // 10% margin from top
        }
        if (!width) {
            width = Math.round(this.canvas.width * 0.90); // 90% of canvas width
        }
        if (!height) {
            height = Math.round(this.canvas.height * 0.82); // 82% of canvas height (leaving space for header/footer)
        }

        this.grid = {
            rows,
            columns,
            x,
            y,
            width,
            height
        };

        // Initialize custom line positions
        this.initializeCustomPositions();

        this.redraw();
    }

    /**
     * Initialize custom line positions with equal spacing
     */
    initializeCustomPositions() {
        if (!this.grid) return;

        const cellWidth = this.grid.width / this.grid.columns;
        const cellHeight = this.grid.height / this.grid.rows;

        // Initialize column positions (vertical lines)
        this.customColPositions = [];
        for (let i = 1; i < this.grid.columns; i++) {
            this.customColPositions.push(this.grid.x + i * cellWidth);
        }

        // Initialize row positions (horizontal lines)
        this.customRowPositions = [];
        for (let i = 1; i < this.grid.rows; i++) {
            this.customRowPositions.push(this.grid.y + i * cellHeight);
        }
    }

    /**
     * Get grid line at point (for dragging)
     */
    getGridLineAtPoint(x, y) {
        if (!this.grid) return null;

        const threshold = 8; // Pixels from line to detect

        // Check vertical lines (columns)
        for (let i = 0; i < this.customColPositions.length; i++) {
            const lineX = this.customColPositions[i];
            if (Math.abs(x - lineX) <= threshold && 
                y >= this.grid.y && 
                y <= this.grid.y + this.grid.height) {
                return { type: 'col', index: i };
            }
        }

        // Check horizontal lines (rows)
        for (let i = 0; i < this.customRowPositions.length; i++) {
            const lineY = this.customRowPositions[i];
            if (Math.abs(y - lineY) <= threshold && 
                x >= this.grid.x && 
                x <= this.grid.x + this.grid.width) {
                return { type: 'row', index: i };
            }
        }

        return null;
    }

    /**
     * Clear grid
     */
    clearGrid() {
        this.grid = null;
        this.voterIdBox = null;
        this.photoBox = null;
        this.nameBox = null;
        this.relativeNameBox = null;
        this.houseNumberBox = null;
        this.genderBox = null;
        this.ageBox = null;
        this.assemblyNumberBox = null;
        this.serialNumberBox = null;
        this.boothCenterBox = null;
        this.boothAddressBox = null;
        this.templateMode = false;
        this.headerTemplateMode = false;
        this.headerTemplateApplied = false;
        this.gridResizeDisabled = false; // Re-enable resize when grid is cleared
        this.customRowPositions = [];
        this.customColPositions = [];
        this.redraw();
    }

    /**
     * Toggle skip zones display
     */
    toggleSkipZones(headerHeight, footerHeight) {
        this.showSkipZones = !this.showSkipZones;
        this.headerHeight = headerHeight;
        this.footerHeight = footerHeight;
        this.redraw();
    }

    /**
     * Enable template mode
     */
    enableTemplateMode() {
        if (!this.grid) {
            alert('Please draw a grid first');
            return false;
        }
        this.templateMode = true;
        this.templateType = 'voterID';
        this.redraw();
        return true;
    }

    /**
     * Disable template mode
     */
    disableTemplateMode() {
        this.templateMode = false;
        this.templateType = null;
        this.redraw();
    }

    /**
     * Check if template is complete
     * At minimum, voter ID is required. Other fields are optional.
     */
    isTemplateComplete() {
        return this.voterIdBox !== null;
    }

    /**
     * Enable header template mode
     */
    enableHeaderTemplateMode() {
        // Header template mode doesn't require a grid - can draw anywhere on page
        this.headerTemplateMode = true;
        this.templateType = 'boothCenter'; // Default to Booth Center
        this.canvas.style.cursor = 'crosshair';
        this.redraw();
        return true;
    }

    /**
     * Disable header template mode
     */
    disableHeaderTemplateMode() {
        this.headerTemplateMode = false;
        this.templateType = null;
        this.canvas.style.cursor = 'default';
        this.redraw();
    }

    /**
     * Check if header template is complete (at least one box defined)
     */
    isHeaderTemplateComplete() {
        return this.boothCenterBox !== null || this.boothAddressBox !== null;
    }

    /**
     * Apply quick template for voter cards with photo on RIGHT
     * Creates standard boxes: voter ID on left, photo on right
     */
    applyQuickTemplate() {
        if (!this.grid) {
            console.error('Grid must be created first');
            return false;
        }

        const firstCell = this.getFirstCell();
        if (!firstCell) {
            console.error('Cannot get first cell');
            return false;
        }

        // Standard voter card layout:
        // - Voter ID text on LEFT (60% of width)
        // - Photo on RIGHT (35% of width with 5% margin)
        
        const cellWidth = firstCell.width;
        const cellHeight = firstCell.height;
        
        // Voter ID box: Left side, 60% width
        this.voterIdBox = {
            x: cellWidth * 0.05,      // 5% margin from left
            y: cellHeight * 0.15,     // 15% from top
            width: cellWidth * 0.55,  // 55% width
            height: cellHeight * 0.35 // 35% height (enough for ID text)
        };
        
        // Photo box: Right side, 35% width
        this.photoBox = {
            x: cellWidth * 0.62,      // 62% from left (right side)
            y: cellHeight * 0.10,     // 10% from top
            width: cellWidth * 0.33,  // 33% width
            height: cellHeight * 0.70 // 70% height (vertical photo)
        };
        
        console.log('✓ Quick template applied (photo on RIGHT)');
        console.log('  Voter ID box:', this.voterIdBox);
        console.log('  Photo box:', this.photoBox);
        
        this.redraw();
        return true;
    }

    /**
     * Get grid configuration (CONVERTED to PDF coordinates)
     * 
     * CRITICAL: Coordinates are drawn on canvas at pdfScale (default 1.5x),
     * but backend needs actual PDF coordinates (scale 1.0).
     * We must divide by pdfScale to convert canvas → PDF coordinates!
     */
    getGridConfig() {
        if (!this.grid) {
            return null;
        }

        // COORDINATE CONVERSION: Canvas → PDF
        // Canvas shows PDF at 1.5x scale, so divide by scale to get actual PDF coordinates
        const scale = this.pdfScale;

        // Calculate cell boundaries based on custom positions
        const colPositions = [this.grid.x, ...this.customColPositions, this.grid.x + this.grid.width];
        const rowPositions = [this.grid.y, ...this.customRowPositions, this.grid.y + this.grid.height];

        // Convert ALL coordinates from canvas to PDF scale
        const convertedColPositions = colPositions.map(pos => pos / scale);
        const convertedRowPositions = rowPositions.map(pos => pos / scale);
        const convertedCustomColPositions = this.customColPositions.map(pos => pos / scale);
        const convertedCustomRowPositions = this.customRowPositions.map(pos => pos / scale);

        const config = {
            rows: this.grid.rows,
            columns: this.grid.columns,
            x: this.grid.x / scale,
            y: this.grid.y / scale,
            width: this.grid.width / scale,
            height: this.grid.height / scale,
            customColPositions: convertedCustomColPositions,
            customRowPositions: convertedCustomRowPositions,
            colPositions: convertedColPositions,
            rowPositions: convertedRowPositions
        };

        console.log('Grid config (canvas):', {
            x: this.grid.x,
            y: this.grid.y,
            width: this.grid.width,
            height: this.grid.height,
            scale: scale
        });
        console.log('Grid config (PDF):', {
            x: config.x,
            y: config.y,
            width: config.width,
            height: config.height
        });

        return config;
    }

    /**
     * Get cell template (CONVERTED to PDF coordinates)
     * 
     * CRITICAL: Template boxes are relative to first cell, but still need
     * to be scaled because they're drawn on the canvas at pdfScale.
     */
    getCellTemplate() {
        // Return template even if only header template is defined
        const hasCellTemplate = this.voterIdBox !== null;
        const hasHeaderTemplate = this.boothCenterBox !== null || this.boothAddressBox !== null;
        
        if (!hasCellTemplate && !hasHeaderTemplate) {
            return null;
        }

        // COORDINATE CONVERSION: Template boxes are relative coordinates,
        // but still need scaling because they were drawn on scaled canvas
        const scale = this.pdfScale;
        
        const convertBox = (box) => {
            if (!box) return null;
            return {
                x: box.x / scale,
                y: box.y / scale,
                width: box.width / scale,
                height: box.height / scale
            };
        };

        const cellTemplate = {
            voterIdBox: convertBox(this.voterIdBox),
            photoBox: convertBox(this.photoBox),
            nameBox: convertBox(this.nameBox),
            relativeNameBox: convertBox(this.relativeNameBox),
            houseNumberBox: convertBox(this.houseNumberBox),
            genderBox: convertBox(this.genderBox),
            ageBox: convertBox(this.ageBox),
            assemblyNumberBox: convertBox(this.assemblyNumberBox),
            serialNumberBox: convertBox(this.serialNumberBox)
        };
        
        // Header template (absolute coordinates, no conversion needed - already in PDF coordinates)
        const headerTemplate = {
            boothCenterBox: this.boothCenterBox ? {
                x: this.boothCenterBox.x / scale,
                y: this.boothCenterBox.y / scale,
                width: this.boothCenterBox.width / scale,
                height: this.boothCenterBox.height / scale
            } : null,
            boothAddressBox: this.boothAddressBox ? {
                x: this.boothAddressBox.x / scale,
                y: this.boothAddressBox.y / scale,
                width: this.boothAddressBox.width / scale,
                height: this.boothAddressBox.height / scale
            } : null
        };
        
        // Remove null entries
        Object.keys(cellTemplate).forEach(key => {
            if (cellTemplate[key] === null) {
                delete cellTemplate[key];
            }
        });
        
        Object.keys(headerTemplate).forEach(key => {
            if (headerTemplate[key] === null) {
                delete headerTemplate[key];
            }
        });
        
        return {
            cellTemplate: cellTemplate,
            headerTemplate: headerTemplate
        };
    }

    /**
     * Redraw canvas
     */
    redraw() {
        // Clear canvas
        this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw skip zones
        if (this.showSkipZones) {
            this.drawSkipZones();
        }

        // Draw grid
        if (this.grid) {
            this.drawGridLines();
        }

        // Draw header template boxes (always visible if defined, drawn at absolute positions)
        // Show on all pages if template is applied
        if (this.headerTemplateMode || this.headerTemplateApplied || this.boothCenterBox || this.boothAddressBox) {
            this.drawHeaderTemplateBoxes();
        }
        
        // Draw cell template boxes
        if (this.grid && (this.templateMode || this.voterIdBox || this.photoBox)) {
            this.drawTemplateBoxes();
        }

        // Draw current rectangle being drawn
        if (this.currentRect && (this.templateMode || this.headerTemplateMode)) {
            const colors = {
                'voterID': '#3b82f6',
                'photo': '#10b981',
                'name': '#f59e0b',
                'relativeName': '#8b5cf6',
                'houseNumber': '#ef4444',
                'gender': '#06b6d4',
                'age': '#ec4899',
                'assemblyNumber': '#14b8a6',
                'serialNumber': '#f97316',
                'boothCenter': '#22c55e',
                'boothAddress': '#eab308'
            };
            this.context.strokeStyle = colors[this.templateType] || '#3b82f6';
            this.context.lineWidth = 3;
            this.context.strokeRect(
                this.currentRect.x,
                this.currentRect.y,
                this.currentRect.width,
                this.currentRect.height
            );
        }
    }

    /**
     * Draw skip zones (header and footer)
     */
    drawSkipZones() {
        // Header zone
        if (this.headerHeight > 0) {
            this.context.fillStyle = 'rgba(239, 68, 68, 0.3)';
            this.context.fillRect(0, 0, this.canvas.width, this.headerHeight);
            this.context.strokeStyle = '#ef4444';
            this.context.lineWidth = 2;
            this.context.strokeRect(0, 0, this.canvas.width, this.headerHeight);
            
            // Label
            this.context.fillStyle = '#ef4444';
            this.context.font = 'bold 16px Inter';
            this.context.fillText('SKIP HEADER', 10, this.headerHeight - 10);
        }

        // Footer zone
        if (this.footerHeight > 0) {
            const footerY = this.canvas.height - this.footerHeight;
            this.context.fillStyle = 'rgba(239, 68, 68, 0.3)';
            this.context.fillRect(0, footerY, this.canvas.width, this.footerHeight);
            this.context.strokeStyle = '#ef4444';
            this.context.lineWidth = 2;
            this.context.strokeRect(0, footerY, this.canvas.width, this.footerHeight);
            
            // Label
            this.context.fillStyle = '#ef4444';
            this.context.font = 'bold 16px Inter';
            this.context.fillText('SKIP FOOTER', 10, footerY + 25);
        }
    }

    /**
     * Draw grid lines
     */
    drawGridLines() {
        // Draw outer border
        this.context.strokeStyle = '#4f46e5';
        this.context.lineWidth = 3;
        this.context.strokeRect(this.grid.x, this.grid.y, this.grid.width, this.grid.height);

        // Draw grid lines
        this.context.strokeStyle = '#818cf8';
        this.context.lineWidth = 2;

        // Vertical lines (using custom positions)
        for (let i = 0; i < this.customColPositions.length; i++) {
            const x = this.customColPositions[i];
            this.context.beginPath();
            this.context.moveTo(x, this.grid.y);
            this.context.lineTo(x, this.grid.y + this.grid.height);
            this.context.stroke();
        }

        // Horizontal lines (using custom positions)
        for (let i = 0; i < this.customRowPositions.length; i++) {
            const y = this.customRowPositions[i];
            this.context.beginPath();
            this.context.moveTo(this.grid.x, y);
            this.context.lineTo(this.grid.x + this.grid.width, y);
            this.context.stroke();
        }

        // Draw cell numbers
        this.drawCellNumbers();

        // Draw resize handles at corners (only when not in template mode and resize is not disabled)
        if (!this.templateMode && !this.gridResizeDisabled) {
            this.drawResizeHandles();
            this.drawLineHandles();
        }
    }

    /**
     * Draw cell numbers based on current grid divisions
     */
    drawCellNumbers() {
        this.context.fillStyle = '#4f46e5';
        this.context.font = 'bold 14px Inter';

        // Calculate all column X positions
        const colPositions = [this.grid.x, ...this.customColPositions, this.grid.x + this.grid.width];
        
        // Calculate all row Y positions
        const rowPositions = [this.grid.y, ...this.customRowPositions, this.grid.y + this.grid.height];

        let cellNum = 1;
        for (let row = 0; row < this.grid.rows; row++) {
            for (let col = 0; col < this.grid.columns; col++) {
                const cellX = colPositions[col] + 5;
                const cellY = rowPositions[row] + 20;
                this.context.fillText(`${cellNum}`, cellX, cellY);
                cellNum++;
            }
        }
    }

    /**
     * Draw visual indicators on draggable lines
     */
    drawLineHandles() {
        const handleSize = 6;

        // Draw handles on vertical lines
        this.customColPositions.forEach(x => {
            const y = this.grid.y + this.grid.height / 2;
            
            // Outer circle
            this.context.fillStyle = '#ffffff';
            this.context.beginPath();
            this.context.arc(x, y, handleSize + 1, 0, 2 * Math.PI);
            this.context.fill();
            
            // Inner circle
            this.context.fillStyle = '#818cf8';
            this.context.beginPath();
            this.context.arc(x, y, handleSize, 0, 2 * Math.PI);
            this.context.fill();
        });

        // Draw handles on horizontal lines
        this.customRowPositions.forEach(y => {
            const x = this.grid.x + this.grid.width / 2;
            
            // Outer circle
            this.context.fillStyle = '#ffffff';
            this.context.beginPath();
            this.context.arc(x, y, handleSize + 1, 0, 2 * Math.PI);
            this.context.fill();
            
            // Inner circle
            this.context.fillStyle = '#818cf8';
            this.context.beginPath();
            this.context.arc(x, y, handleSize, 0, 2 * Math.PI);
            this.context.fill();
        });
    }

    /**
     * Draw resize handles at grid corners
     */
    drawResizeHandles() {
        const handleSize = 12;
        const corners = [
            { x: this.grid.x, y: this.grid.y }, // topLeft
            { x: this.grid.x + this.grid.width, y: this.grid.y }, // topRight
            { x: this.grid.x, y: this.grid.y + this.grid.height }, // bottomLeft
            { x: this.grid.x + this.grid.width, y: this.grid.y + this.grid.height } // bottomRight
        ];

        corners.forEach(corner => {
            // Outer circle (white)
            this.context.fillStyle = '#ffffff';
            this.context.beginPath();
            this.context.arc(corner.x, corner.y, handleSize / 2 + 2, 0, 2 * Math.PI);
            this.context.fill();

            // Inner circle (primary color)
            this.context.fillStyle = '#4f46e5';
            this.context.beginPath();
            this.context.arc(corner.x, corner.y, handleSize / 2, 0, 2 * Math.PI);
            this.context.fill();

            // Border
            this.context.strokeStyle = '#ffffff';
            this.context.lineWidth = 2;
            this.context.stroke();
        });
    }

    /**
     * Draw template boxes
     */
    drawTemplateBoxes() {
        const firstCell = this.getFirstCell();
        if (!firstCell) return;

        // Box definitions with colors and labels
        const boxDefinitions = [
            { box: this.voterIdBox, color: '#3b82f6', label: 'Voter ID (Ctrl+1)', alpha: 0.2 },
            { box: this.nameBox, color: '#f59e0b', label: 'Name (Ctrl+2)', alpha: 0.2 },
            { box: this.relativeNameBox, color: '#8b5cf6', label: 'Relative Name (Ctrl+3)', alpha: 0.2 },
            { box: this.houseNumberBox, color: '#ef4444', label: 'House Number (Ctrl+4)', alpha: 0.2 },
            { box: this.genderBox, color: '#06b6d4', label: 'Gender (Ctrl+5)', alpha: 0.2 },
            { box: this.ageBox, color: '#ec4899', label: 'Age (Ctrl+6)', alpha: 0.2 },
            { box: this.assemblyNumberBox, color: '#14b8a6', label: 'Assembly Number (Ctrl+7)', alpha: 0.2 },
            { box: this.photoBox, color: '#10b981', label: 'Photo (Ctrl+8)', alpha: 0.2 },
            { box: this.serialNumberBox, color: '#f97316', label: 'Serial Number (Ctrl+9)', alpha: 0.2 }
        ];

        // Show boxes in template mode OR if boxes exist
        const showOnFirstCell = this.templateMode || boxDefinitions.some(def => def.box !== null);

        if (showOnFirstCell) {
            // Draw all boxes on first cell
            boxDefinitions.forEach((def) => {
                if (def.box) {
                    // Convert hex to rgba
                    const hex = def.color.replace('#', '');
                    const r = parseInt(hex.substr(0, 2), 16);
                    const g = parseInt(hex.substr(2, 2), 16);
                    const b = parseInt(hex.substr(4, 2), 16);
                    
                    this.context.strokeStyle = def.color;
                    this.context.lineWidth = 3;
                    this.context.strokeRect(
                        firstCell.x + def.box.x,
                        firstCell.y + def.box.y,
                        def.box.width,
                        def.box.height
                    );
                    this.context.fillStyle = `rgba(${r}, ${g}, ${b}, ${def.alpha})`;
                    this.context.fillRect(
                        firstCell.x + def.box.x,
                        firstCell.y + def.box.y,
                        def.box.width,
                        def.box.height
                    );
                    
                    // Label
                    this.context.fillStyle = def.color;
                    this.context.font = 'bold 11px Inter';
                    this.context.fillText(
                        def.label.split(' ')[0], // Just show the field name
                        firstCell.x + def.box.x + 5,
                        firstCell.y + def.box.y - 5
                    );
                }
            });

            // Highlight first cell (only in template mode)
            if (this.templateMode) {
                this.context.strokeStyle = '#f59e0b';
                this.context.lineWidth = 3;
                this.context.setLineDash([10, 5]);
                this.context.strokeRect(firstCell.x, firstCell.y, firstCell.width, firstCell.height);
                this.context.setLineDash([]);
            }
        }
        
        // If template is applied (not in template mode but boxes exist), show on ALL cells
        if (!this.templateMode && this.voterIdBox) {
            this.drawTemplateOnAllCells();
        }
    }

    /**
     * Draw template boxes on all grid cells (after template is applied)
     * Applies ALL defined boxes (voter ID, name, relative name, house number, gender, age, assembly number, photo)
     */
    drawTemplateOnAllCells() {
        const colPositions = [this.grid.x, ...this.customColPositions, this.grid.x + this.grid.width];
        const rowPositions = [this.grid.y, ...this.customRowPositions, this.grid.y + this.grid.height];

        // Define all boxes with their colors and labels
        const boxDefinitions = [
            { box: this.voterIdBox, color: '#3b82f6', alpha: 0.1 },
            { box: this.nameBox, color: '#f59e0b', alpha: 0.1 },
            { box: this.relativeNameBox, color: '#8b5cf6', alpha: 0.1 },
            { box: this.houseNumberBox, color: '#ef4444', alpha: 0.1 },
            { box: this.genderBox, color: '#06b6d4', alpha: 0.1 },
            { box: this.ageBox, color: '#ec4899', alpha: 0.1 },
            { box: this.assemblyNumberBox, color: '#14b8a6', alpha: 0.1 },
            { box: this.photoBox, color: '#10b981', alpha: 0.1 },
            { box: this.serialNumberBox, color: '#f97316', alpha: 0.1 }
        ];

        // Draw template on each cell
        for (let row = 0; row < this.grid.rows; row++) {
            for (let col = 0; col < this.grid.columns; col++) {
                const cellX = colPositions[col];
                const cellY = rowPositions[row];
                const cellWidth = colPositions[col + 1] - colPositions[col];
                const cellHeight = rowPositions[row + 1] - rowPositions[row];

                // Scale the template boxes to fit the cell
                const scaleX = cellWidth / this.getFirstCell().width;
                const scaleY = cellHeight / this.getFirstCell().height;

                // Draw all defined boxes
                boxDefinitions.forEach((def) => {
                    if (def.box) {
                        const scaledX = cellX + def.box.x * scaleX;
                        const scaledY = cellY + def.box.y * scaleY;
                        const scaledWidth = def.box.width * scaleX;
                        const scaledHeight = def.box.height * scaleY;

                        // Draw stroke
                        this.context.strokeStyle = def.color;
                        this.context.lineWidth = 2;
                        this.context.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

                        // Draw fill
                        this.context.fillStyle = this._hexToRgba(def.color, def.alpha);
                        this.context.fillRect(scaledX, scaledY, scaledWidth, scaledHeight);
                    }
                });
            }
        }
    }

    /**
     * Helper function to convert hex color to rgba string
     */
    _hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    /**
     * Get first cell coordinates
     */
    getFirstCell() {
        if (!this.grid) {
            return null;
        }

        const colPositions = [this.grid.x, ...this.customColPositions, this.grid.x + this.grid.width];
        const rowPositions = [this.grid.y, ...this.customRowPositions, this.grid.y + this.grid.height];

        return {
            x: colPositions[0],
            y: rowPositions[0],
            width: colPositions[1] - colPositions[0],
            height: rowPositions[1] - rowPositions[0]
        };
    }

    /**
     * Check if point is in grid
     */
    isPointInGrid(x, y) {
        if (!this.grid) {
            return false;
        }

        return x >= this.grid.x &&
               x <= this.grid.x + this.grid.width &&
               y >= this.grid.y &&
               y <= this.grid.y + this.grid.height;
    }

    /**
     * Get resize handle at point
     */
    getResizeHandle(x, y) {
        if (!this.grid) {
            return null;
        }

        const handleSize = 20; // Size of the clickable corner area
        const corners = {
            topLeft: {
                x: this.grid.x,
                y: this.grid.y
            },
            topRight: {
                x: this.grid.x + this.grid.width,
                y: this.grid.y
            },
            bottomLeft: {
                x: this.grid.x,
                y: this.grid.y + this.grid.height
            },
            bottomRight: {
                x: this.grid.x + this.grid.width,
                y: this.grid.y + this.grid.height
            }
        };

        for (const [handle, corner] of Object.entries(corners)) {
            if (Math.abs(x - corner.x) <= handleSize && Math.abs(y - corner.y) <= handleSize) {
                return handle;
            }
        }

        return null;
    }

    /**
     * Update cursor based on resize handle
     */
    updateCursor(handle) {
        const cursors = {
            topLeft: 'nwse-resize',
            topRight: 'nesw-resize',
            bottomLeft: 'nesw-resize',
            bottomRight: 'nwse-resize'
        };
        this.canvas.style.cursor = cursors[handle] || 'default';
    }

    /**
     * Draw header template boxes (absolute positions on page)
     */
    drawHeaderTemplateBoxes() {
        const boxDefinitions = [
            { box: this.boothCenterBox, color: '#22c55e', label: 'Booth Center (Ctrl+F2)', alpha: 0.3 },
            { box: this.boothAddressBox, color: '#eab308', label: 'Booth Address (Ctrl+F3)', alpha: 0.3 }
        ];
        
        boxDefinitions.forEach((def) => {
            if (def.box) {
                // Header boxes are in absolute coordinates (no conversion needed)
                const hex = def.color.replace('#', '');
                const r = parseInt(hex.substr(0, 2), 16);
                const g = parseInt(hex.substr(2, 2), 16);
                const b = parseInt(hex.substr(4, 2), 16);
                
                // Draw filled rectangle
                this.context.fillStyle = `rgba(${r}, ${g}, ${b}, ${def.alpha})`;
                this.context.fillRect(def.box.x, def.box.y, def.box.width, def.box.height);
                
                // Draw border
                this.context.strokeStyle = def.color;
                this.context.lineWidth = 2;
                this.context.strokeRect(def.box.x, def.box.y, def.box.width, def.box.height);
                
                // Draw label (show in template mode or when applied)
                if (this.headerTemplateMode || this.headerTemplateApplied) {
                    this.context.fillStyle = def.color;
                    this.context.font = 'bold 12px Arial';
                    this.context.fillText(def.label, def.box.x + 5, def.box.y + 15);
                    
                    // Add "Applied to All Pages" indicator when template is applied
                    if (this.headerTemplateApplied) {
                        this.context.fillStyle = '#000000';
                        this.context.font = '10px Arial';
                        this.context.fillText('(All Pages)', def.box.x + 5, def.box.y + 28);
                    }
                }
            }
        });
    }

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        // This will be handled by app.js
        window.dispatchEvent(new CustomEvent('showToast', {
            detail: { message, type }
        }));
    }
}


