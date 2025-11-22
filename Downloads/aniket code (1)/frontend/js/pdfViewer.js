/**
 * PDF Viewer Module
 * Handles PDF rendering using PDF.js
 */

class PDFViewer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.context = this.canvas.getContext('2d');
        this.pdfDoc = null;
        this.currentPage = 1;
        this.totalPages = 0;
        this.scale = 1.5;
        this.rendering = false;
        this.currentBlobUrl = null;
        this.loadingTask = null;
        
        // Initialize PDF.js worker
        if (typeof pdfjsLib !== 'undefined') {
            pdfjsLib.GlobalWorkerOptions.workerSrc = 
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        }
    }

    /**
     * Load PDF from file
     */
    async loadPDF(file) {
        try {
            this._cleanupCurrentDocument();

            this.currentBlobUrl = URL.createObjectURL(file);
            this.loadingTask = pdfjsLib.getDocument({
                url: this.currentBlobUrl,
                disableAutoFetch: false,
                disableStream: false,
                rangeChunkSize: 4 * 1024 * 1024 // 4MB chunks keep memory usage predictable
            });

            this.pdfDoc = await this.loadingTask.promise;
            this.totalPages = this.pdfDoc.numPages;

            console.log(`PDF loaded: ${this.totalPages} pages`);

            await this.renderPage(1);

            return {
                totalPages: this.totalPages
            };
        } catch (error) {
            console.error('PDF load error:', error);
            let message = error?.message || 'Unknown viewer error';

            if (error?.name === 'InvalidPDFException' || /Invalid PDF structure/i.test(message)) {
                message = 'Viewer could not parse the PDF structure. This usually means the browser ran out of memory while opening a very large file. The PDF itself can still be processed after upload.';
            }

            throw new Error('Failed to load PDF: ' + message);
        } finally {
            this.loadingTask = null;
        }
    }

    /**
     * Render a specific page
     */
    async renderPage(pageNum) {
        if (this.rendering || !this.pdfDoc) {
            return;
        }

        if (pageNum < 1 || pageNum > this.totalPages) {
            return;
        }

        this.rendering = true;
        this.currentPage = pageNum;

        try {
            const page = await this.pdfDoc.getPage(pageNum);
            const viewport = page.getViewport({ scale: this.scale });

            // Set canvas dimensions
            this.canvas.width = viewport.width;
            this.canvas.height = viewport.height;

            // Set canvas display size - allow scrolling if larger than viewport
            // Keep actual canvas size for quality, but allow CSS to scale for display
            this.canvas.style.width = viewport.width + 'px';
            this.canvas.style.height = viewport.height + 'px';
            this.canvas.style.display = 'block';
            
            // Ensure canvas container matches canvas size
            const canvasContainer = this.canvas.parentElement;
            if (canvasContainer && canvasContainer.classList.contains('canvas-container')) {
                canvasContainer.style.width = viewport.width + 'px';
                canvasContainer.style.height = viewport.height + 'px';
            }

            // Render page
            const renderContext = {
                canvasContext: this.context,
                viewport: viewport
            };

            await page.render(renderContext).promise;

            console.log(`Rendered page ${pageNum}`);

            // Emit event for overlay canvas to match size AND SCALE
            window.dispatchEvent(new CustomEvent('pdfPageRendered', {
                detail: {
                    width: viewport.width,
                    height: viewport.height,
                    pageNum: pageNum,
                    scale: this.scale  // CRITICAL: Grid overlay needs this for coordinate conversion!
                }
            }));

        } catch (error) {
            console.error('Page render error:', error);
        } finally {
            this.rendering = false;
        }
    }

    /**
     * Go to next page
     */
    async nextPage() {
        if (this.currentPage < this.totalPages) {
            await this.renderPage(this.currentPage + 1);
        }
    }

    /**
     * Go to previous page
     */
    async prevPage() {
        if (this.currentPage > 1) {
            await this.renderPage(this.currentPage - 1);
        }
    }

    /**
     * Zoom in
     */
    async zoomIn() {
        this.scale += 0.25;
        await this.renderPage(this.currentPage);
    }

    /**
     * Zoom out
     */
    async zoomOut() {
        if (this.scale > 0.5) {
            this.scale -= 0.25;
            await this.renderPage(this.currentPage);
        }
    }

    /**
     * Get current zoom level
     */
    getZoomLevel() {
        return Math.round(this.scale * 100);
    }

    /**
     * Get canvas dimensions
     */
    getCanvasDimensions() {
        return {
            width: this.canvas.width,
            height: this.canvas.height
        };
    }

    /**
     * Clean up current PDF resources when switching files
     */
    _cleanupCurrentDocument() {
        if (this.loadingTask) {
            try {
                this.loadingTask.destroy();
            } catch (err) {
                console.warn('Error while cancelling previous PDF load:', err);
            }
            this.loadingTask = null;
        }

        if (this.pdfDoc) {
            try {
                this.pdfDoc.destroy();
            } catch (err) {
                console.warn('Error while destroying previous PDF document:', err);
            }
            this.pdfDoc = null;
        }

        if (this.currentBlobUrl) {
            URL.revokeObjectURL(this.currentBlobUrl);
            this.currentBlobUrl = null;
        }
    }
}


