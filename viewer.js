      const BW_DIR = (typeof window.BW_DIR === "string" && window.BW_DIR) ? window.BW_DIR : "./local_bw";
      const COLOR_DIR = (typeof window.COLOR_DIR === "string" && window.COLOR_DIR) ? window.COLOR_DIR : "./local_color";
      const gallery = document.getElementById('gallery');
      const count = document.getElementById('count');
      const debugPanel = document.getElementById('debug');
      const debugLog = document.getElementById('log');
      const debugToggle = document.getElementById('debugToggle');
      const statusNote = document.getElementById('statusNote');
      const stats = { total: 0, loaded: 0, failed: 0 };
      const failed = [];
      const MAX_LISTED_FAILURES = 20;
      const DEFAULT_ASPECT = 4 / 3;
      const pairRatios = new Array(pairsBw.length);
      const OPEN_ANIMATION_MS = 920;
      const CLOSE_ANIMATION_MS = 920;
      function setTileAspect(index, tile, width, height) {
        if (!width || !height) {
          return;
        }
        const ratio = width / height;
        if (!Number.isFinite(ratio) || ratio <= 0) {
          return;
        }
        pairRatios[index] = ratio;
        tile.style.setProperty('--frame-aspect-ratio', String(ratio));
      }

      const zoomState = {
        sourceTile: null,
        overlayTile: null,
        backdrop: null,
        startRect: null,
        status: 'idle',
        index: -1,
        openTimer: null,
        closeTimer: null
      };
      const protocolHint = {
        file: '',
        http: 'If you are serving via HTTP/HTTPS, local file:// URLs are blocked by browsers. Open this page directly as a file:// URL, or run a local server that exposes both image folders.',
        https: 'If you are serving via HTTPS, local file:// URLs are blocked by browsers. Open this page directly as a file:// URL, or run a local server that exposes both image folders.'
      };

      function getCenteredRect(aspectRatio) {
        const maxW = Math.floor(window.innerWidth * 0.86);
        const maxH = Math.floor(window.innerHeight * 0.86);
        const ratio = aspectRatio > 0 ? aspectRatio : DEFAULT_ASPECT;
        let width = maxW;
        let height = Math.round(width / ratio);

        if (height > maxH) {
          height = maxH;
          width = Math.round(height * ratio);
        }

        return {
          width,
          height,
          left: Math.max(0, Math.round((window.innerWidth - width) / 2)),
          top: Math.max(0, Math.round((window.innerHeight - height) / 2))
        };
      }

      function cleanupZoom() {
        if (zoomState.backdrop) {
          zoomState.backdrop.remove();
        }
        if (zoomState.openTimer) {
          window.clearTimeout(zoomState.openTimer);
        }
        if (zoomState.closeTimer) {
          window.clearTimeout(zoomState.closeTimer);
        }
        zoomState.sourceTile = null;
        zoomState.overlayTile = null;
        zoomState.backdrop = null;
        zoomState.startRect = null;
        zoomState.index = -1;
        zoomState.openTimer = null;
        zoomState.closeTimer = null;
        zoomState.status = 'idle';
      }

      function closeZoom() {
        if (!['opening', 'expanded'].includes(zoomState.status)) {
          return;
        }

        const { overlayTile, startRect, sourceTile } = zoomState;
        if (!overlayTile || !startRect || !sourceTile) {
          cleanupZoom();
          return;
        }

        zoomState.status = 'closing';
        if (zoomState.openTimer) {
          window.clearTimeout(zoomState.openTimer);
          zoomState.openTimer = null;
        }
        overlayTile.style.top = `${startRect.top}px`;
        overlayTile.style.left = `${startRect.left}px`;
        overlayTile.style.width = `${startRect.width}px`;
        overlayTile.style.height = `${startRect.height}px`;

        let done = false;
        const finalize = () => {
          if (done) {
            return;
          }
          done = true;
          sourceTile.classList.toggle('revealed', overlayTile.classList.contains('revealed'));
          cleanupZoom();
        };

        const finalizeClose = (evt) => {
          if (evt.target !== overlayTile || evt.propertyName !== 'top') {
            return;
          }
          overlayTile.removeEventListener('transitionend', finalizeClose);
          finalize();
        };

        overlayTile.addEventListener('transitionend', finalizeClose);
        zoomState.closeTimer = window.setTimeout(finalize, CLOSE_ANIMATION_MS + 40);
      }

      function openZoom(sourceTile, index) {
        if (zoomState.status !== 'idle' || !sourceTile) {
          return;
        }

        const sourceFrame = sourceTile.querySelector('.frame');
        const sourceRect = sourceFrame.getBoundingClientRect();
        if (!sourceRect.width || !sourceRect.height) {
          sourceTile.classList.toggle('revealed');
          return;
        }

        const overlay = sourceTile.cloneNode(true);
        overlay.className = 'tile-overlay';
        overlay.dataset.zoomed = 'true';
        overlay.style.top = `${sourceRect.top}px`;
        overlay.style.left = `${sourceRect.left}px`;
        overlay.style.width = `${sourceRect.width}px`;
        overlay.style.height = `${sourceRect.height}px`;
        overlay.classList.remove('revealed');
        const overlayCaption = overlay.querySelector('.caption');
        if (overlayCaption) {
          overlayCaption.style.display = 'none';
        }
        overlay.addEventListener('click', (event) => {
          if (zoomState.status === 'expanded' || zoomState.status === 'opening') {
            event.preventDefault();
            event.stopPropagation();
            overlay.classList.toggle('revealed');
            sourceTile.classList.toggle('revealed');
          }
        });

        const backdrop = document.createElement('div');
        backdrop.className = 'gallery-backdrop';
        backdrop.appendChild(overlay);
        document.body.appendChild(backdrop);
        requestAnimationFrame(() => {
          backdrop.classList.add('active');
        });

        zoomState.sourceTile = sourceTile;
        zoomState.overlayTile = overlay;
        zoomState.backdrop = backdrop;
        zoomState.startRect = {
          top: sourceRect.top,
          left: sourceRect.left,
          width: sourceRect.width,
          height: sourceRect.height
        };
        zoomState.status = 'opening';
        zoomState.index = index;

        backdrop.addEventListener('click', (event) => {
          if (event.target !== backdrop) {
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          closeZoom();
        });

        const centered = getCenteredRect(pairRatios[index] || DEFAULT_ASPECT);
        requestAnimationFrame(() => {
          overlay.style.top = `${centered.top}px`;
          overlay.style.left = `${centered.left}px`;
          overlay.style.width = `${centered.width}px`;
          overlay.style.height = `${centered.height}px`;
        });

        let done = false;
        const finishOpen = (evt) => {
          if (zoomState.status !== 'opening' || zoomState.overlayTile !== overlay) {
            return;
          }
          if (done) {
            return;
          }
          if (evt && evt.target && (evt.target !== overlay || evt.propertyName !== 'top')) {
            return;
          }
          done = true;
          overlay.removeEventListener('transitionend', finishOpen);
          overlay.classList.add('revealed');
          zoomState.status = 'expanded';
          sourceTile.classList.remove('revealed');
          if (zoomState.openTimer) {
            window.clearTimeout(zoomState.openTimer);
            zoomState.openTimer = null;
          }
        };

        overlay.addEventListener('transitionend', finishOpen);
        zoomState.openTimer = window.setTimeout(() => {
          if (done) {
            return;
          }
          finishOpen({ target: overlay, propertyName: 'top' });
        }, OPEN_ANIMATION_MS + 40);
      }

      function logEvent(type, message) {
        const line = document.createElement('div');
        line.className = `log-entry ${type}`;
        line.textContent = `[${new Date().toLocaleTimeString()}] [${type}] ${message}`;
        console.log(line.textContent);
        debugLog.appendChild(line);
        debugLog.scrollTop = debugLog.scrollHeight;
      }

      function logImageStatus(kind, name, path, ok) {
        if (ok) {
          stats.loaded += 1;
          if (stats.loaded + stats.failed === stats.total) {
            logEvent('info', `Load complete. Loaded: ${stats.loaded}, Failed: ${stats.failed}`);
            if (stats.failed === 0) {
              if (location.protocol !== 'file:') {
                statusNote.textContent = protocolHint[location.protocol.replace(':', '')] || '';
              } else {
                statusNote.textContent = '';
              }
            }
            if (stats.failed > 0) {
              statusNote.textContent = `Loaded: ${stats.loaded}. Failed: ${stats.failed}. Check console or log entries for the first ${Math.min(failed.length, MAX_LISTED_FAILURES)} missing files.`;
            }
          }
          return;
        }

        stats.failed += 1;
        debugPanel.style.display = 'block';
        failed.push({ kind, name, path });
        logEvent('error', `${kind} failed: ${name} -> ${path}`);
        if (failed.length === 1 && location.protocol !== 'file:') {
          statusNote.textContent = protocolHint[location.protocol.replace(':', '')] || protocolHint.http;
        }

        if (failed.length <= MAX_LISTED_FAILURES) {
          const sample = failed.map(f => `${f.kind}: ${f.name}`).join(' | ');
          statusNote.textContent = `Load failures (${failed.length}): ${sample}`;
        }

        if (stats.loaded + stats.failed === stats.total) {
          statusNote.textContent = `Load complete. Loaded: ${stats.loaded}, Failed: ${stats.failed}.`;
          logEvent('error', `Load complete. Loaded: ${stats.loaded}, Failed: ${stats.failed}`);
        }
      }

      window.addEventListener('error', (evt) => {
        const message = `Global error: ${evt.message || evt.error?.message || 'Unknown error'}`;
        logEvent('error', message);
      });

      window.addEventListener('unhandledrejection', (evt) => {
        const reason = evt.reason;
        const reasonMessage = reason?.message || String(reason);
        logEvent('error', `Unhandled Promise rejection: ${reasonMessage}`);
      });


      debugToggle.addEventListener('click', () => {
        debugPanel.style.display = debugPanel.style.display === 'none' ? 'block' : 'none';
        debugToggle.textContent = debugPanel.style.display === 'none' ? 'Show' : 'Hide';
      });

      if (!pairsBw || pairsBw.length === 0) {
        const msg = 'No matching filenames were found.';
        count.textContent = msg;
        logEvent('error', msg);
      } else {
        const msg = `${pairsBw.length} matching pairs loaded.`;
        count.textContent = msg;
        logEvent('info', msg);
      }

      stats.total = pairsBw.length * 2;
      logEvent('info', `Page loaded via ${location.protocol}`);

      for (let i = 0; i < pairsBw.length; i++) {
        const bwName = pairsBw[i];
        const colorName = pairsColor[i];

        const tile = document.createElement('button');
        tile.type = 'button';
        tile.className = 'tile';
        tile.setAttribute('aria-label', `Reveal color version of ${bwName}`);

        const frame = document.createElement('div');
        frame.className = 'frame';

        const colorSrc = `${COLOR_DIR}/${encodeURIComponent(colorName)}`;
        const bwSrc = `${BW_DIR}/${encodeURIComponent(bwName)}`;

        const color = new Image();
        color.className = 'color';
        color.loading = 'lazy';
        color.decoding = 'async';
        color.alt = `${bwName} color`;
        color.src = colorSrc;

        const bw = new Image();
        bw.className = 'bw';
        bw.loading = 'lazy';
        bw.decoding = 'async';
        bw.alt = `${bwName} black and white`;
        bw.src = bwSrc;

        color.addEventListener('load', () => {
          setTileAspect(i, tile, color.naturalWidth, color.naturalHeight);
          logImageStatus('Color', colorName, colorSrc, true);
        });
        color.addEventListener('error', () => { logImageStatus('Color', colorName, colorSrc, false); });
        bw.addEventListener('load', () => {
          setTileAspect(i, tile, bw.naturalWidth, bw.naturalHeight);
          logImageStatus('B/W', bwName, bwSrc, true);
        });
        bw.addEventListener('error', () => { logImageStatus('B/W', bwName, bwSrc, false); });

        frame.appendChild(color);
        frame.appendChild(bw);

        const caption = document.createElement('div');
        caption.className = 'caption';
        caption.textContent = bwName;

        tile.appendChild(frame);
        tile.appendChild(caption);

        tile.addEventListener('click', (event) => {
          if (zoomState.status === 'expanded') {
            if (zoomState.sourceTile === tile) {
              event.preventDefault();
              event.stopPropagation();
              closeZoom();
            }
            return;
          }

          if (zoomState.status !== 'idle') {
            event.preventDefault();
            event.stopPropagation();
            return;
          }

          if (tile.classList.contains('revealed')) {
            tile.classList.remove('revealed');
            return;
          }

          event.preventDefault();
          openZoom(tile, i);
        });

        gallery.appendChild(tile);
      }
