      const BW_DIR = (typeof window.BW_DIR === 'string' && window.BW_DIR) ? window.BW_DIR : './local_bw';
      const HIGH_DIR = (typeof window.HIGH_DIR === 'string' && window.HIGH_DIR) ? window.HIGH_DIR : './local_color';
      const COLOR_DIR = (typeof window.COLOR_DIR === 'string' && window.COLOR_DIR) ? window.COLOR_DIR : HIGH_DIR;
      const RATING_SCOPE = (typeof window.RATING_SCOPE === 'string' && window.RATING_SCOPE) ? window.RATING_SCOPE : location.pathname;
      const RATING_STORAGE_KEY = 'photoPairViewerRatingsV1';
      const RATING_MODE_KEY = 'photoPairViewerDownModesV1';

      const gallery = document.getElementById('gallery');
      const count = document.getElementById('count');
      const debugPanel = document.getElementById('debug');
      const debugLog = document.getElementById('log');
      const debugToggle = document.getElementById('debugToggle');
      const statusNote = document.getElementById('statusNote');
      const ratingSummary = document.getElementById('ratingSummary');
      const shortcutHint = document.getElementById('shortcutHint');

      const pairRatios = new Array(pairsBw.length);
      const OPEN_ANIMATION_MS = 920;
      const CLOSE_ANIMATION_MS = 920;
      const DEFAULT_ASPECT = 4 / 3;
      const MAX_LISTED_FAILURES = 20;
      const STATS_LAYER_COUNT = 3;
      const PLATFORM_IS_MAC = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform || '');

      if (debugPanel && debugPanel.style.display === '') {
        debugPanel.style.display = 'none';
      }
      if (debugToggle) {
        debugToggle.textContent = debugPanel && debugPanel.style.display === 'none' ? 'Show logs' : 'Hide logs';
      }

      const stats = { total: 0, loaded: 0, failed: 0 };
      const failed = [];
      const ratings = Object.create(null);
      const ratingModes = Object.create(null);
      const nonBwModeByIndex = Object.create(null);
      let hasStoredRatings = false;
      let hasStoredRatingModes = false;

      const zoomState = {
        sourceTile: null,
        overlayTile: null,
        backdrop: null,
        startRect: null,
        status: 'idle',
        index: -1,
        mode: 'bw',
        openTimer: null,
        closeTimer: null,
        selectedIndex: -1,
        nonBwMode: 'high',
        singleClickTimer: null,
        isNavigating: false,
        queuedNavigation: [],
        navigationTimer: null,
        isModeFading: false,
        modeFadeImage: null,
        modeFadeHandler: null
      };

      const protocolHint = {
        file: '',
        http: 'If you are serving via HTTP/HTTPS, local file:// URLs are blocked by browsers. Open this page directly as a file:// URL, or run a local server that exposes both image folders.',
        https: 'If you are serving via HTTPS, local file:// URLs are blocked by browsers. Open this page directly as a file:// URL, or run a local server that exposes both image folders.'
      };

      function clampMode(mode) {
        if (mode === 'high' || mode === 'color') {
          return mode;
        }
        return 'bw';
      }

      function applyTileMode(tile, mode) {
        const normalizedMode = clampMode(mode);
        tile.classList.remove('mode-bw', 'mode-high', 'mode-color');
        tile.classList.add(`mode-${normalizedMode}`);
        tile.dataset.mode = normalizedMode;

        const bwImage = tile.querySelector('.bw');
        const highImage = tile.querySelector('.high');
        const colorImage = tile.querySelector('.color');

        if (bwImage) {
          bwImage.style.opacity = normalizedMode === 'bw' ? '1' : '0';
        }
        if (highImage) {
          highImage.style.opacity = normalizedMode === 'high' ? '1' : '0';
        }
        if (colorImage) {
          colorImage.style.opacity = normalizedMode === 'color' ? '1' : '0';
        }
      }

      function getStoredNonBwMode(index) {
        const mode = nonBwModeByIndex[index];
        if (mode === 'color') {
          return 'color';
        }
        return 'high';
      }

      function setStoredNonBwMode(index, mode) {
        if (index < 0) {
          return;
        }
        nonBwModeByIndex[index] = (mode === 'color') ? 'color' : 'high';
      }

      function applyZoomMode(overlay, nextMode) {
        const normalizedMode = clampMode(nextMode);
        const previousMode = zoomState.mode;
        if (previousMode === normalizedMode) {
          if (normalizedMode !== 'bw' && zoomState.index >= 0) {
            zoomState.nonBwMode = normalizedMode;
            setStoredNonBwMode(zoomState.index, normalizedMode);
          }
          return;
        }

        if (zoomState.modeFadeImage && zoomState.modeFadeHandler) {
          zoomState.modeFadeImage.removeEventListener('transitionend', zoomState.modeFadeHandler);
        }
        zoomState.modeFadeImage = null;
        zoomState.modeFadeHandler = null;
        zoomState.isModeFading = false;

        zoomState.mode = normalizedMode;
        applyTileMode(overlay, normalizedMode);
        if (normalizedMode !== 'bw' && zoomState.index >= 0) {
          zoomState.nonBwMode = normalizedMode;
          setStoredNonBwMode(zoomState.index, normalizedMode);
          persistRatingModes();
        }

        if (!overlay || !overlay.classList || !overlay.classList.contains('tile-overlay') || zoomState.status !== 'expanded') {
          zoomState.isModeFading = false;
          return;
        }

        const fadeImage = overlay.querySelector(`.${normalizedMode}`);
        if (!fadeImage) {
          zoomState.isModeFading = false;
          return;
        }

        zoomState.isModeFading = true;
        zoomState.modeFadeImage = fadeImage;
        zoomState.modeFadeHandler = (evt) => {
          if (!evt || evt.target !== fadeImage || evt.propertyName !== 'opacity') {
            return;
          }
          if (!zoomState.modeFadeImage || !zoomState.modeFadeHandler || !zoomState.isModeFading) {
            return;
          }
          if (zoomState.modeFadeImage === fadeImage) {
            zoomState.modeFadeImage.removeEventListener('transitionend', zoomState.modeFadeHandler);
            zoomState.modeFadeImage = null;
            zoomState.modeFadeHandler = null;
            zoomState.isModeFading = false;
            if (zoomState.status === 'expanded' && zoomState.overlayTile === overlay) {
              flushQueuedNavigation();
            }
          }
        };
        fadeImage.addEventListener('transitionend', zoomState.modeFadeHandler);
      }

      function toggleBwMode(overlay) {
        if (!overlay || (zoomState.status !== 'expanded' && zoomState.status !== 'opening')) {
          return;
        }
        const nextMode = (zoomState.mode === 'bw') ? zoomState.nonBwMode : 'bw';
        applyZoomMode(overlay, nextMode);
      }

      function toggleHighColorMode(overlay) {
        if (!overlay || (zoomState.status !== 'expanded' && zoomState.status !== 'opening')) {
          return;
        }
        if (zoomState.mode === 'high') {
          applyZoomMode(overlay, 'color');
          return;
        }
        if (zoomState.mode === 'color') {
          applyZoomMode(overlay, 'high');
        }
      }

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

      function normalizeRatingValue(value) {
        if (value === 'up' || value === 'down') {
          return value;
        }
        return null;
      }

      function ratingKey(index) {
        return `${RATING_SCOPE}::${pairsBw[index] || ''}`;
      }

      function getRating(index) {
        return ratings[ratingKey(index)] || null;
      }

      function persistRatings() {
        if (!hasStoredRatings) {
          return;
        }

        try {
          localStorage.setItem(RATING_STORAGE_KEY, JSON.stringify(ratings));
        } catch (_error) {
          // localStorage is unavailable in some browser modes.
        }
      }

      function persistRatingModes() {
        if (!hasStoredRatingModes) {
          return;
        }

        try {
          localStorage.setItem(RATING_MODE_KEY, JSON.stringify(ratingModes));
        } catch (_error) {
          // localStorage is unavailable in some browser modes.
        }
      }

      function ratingModeKey(index) {
        return `${RATING_SCOPE}::${pairsBw[index] || ''}::mode`;
      }

      function getStoredRatingMode(index) {
        const storedMode = ratingModes[ratingModeKey(index)];
        if (storedMode === 'color') {
          return 'color';
        }
        return 'high';
      }

      function setStoredRatingMode(index, mode) {
        const key = ratingModeKey(index);
        if (mode === 'color') {
          ratingModes[key] = 'color';
          return;
        }
        delete ratingModes[key];
      }

      function clearStoredRatingMode(index) {
        delete ratingModes[ratingModeKey(index)];
      }

      function getActiveRatingMode(index) {
        if (zoomState.index === index && zoomState.mode === 'high') {
          return 'high';
        }
        if (zoomState.index === index && zoomState.mode === 'color') {
          return 'color';
        }
        return getStoredNonBwMode(index);
      }

      function loadRatings() {
        try {
          const stored = localStorage.getItem(RATING_STORAGE_KEY);
          if (!stored) {
            hasStoredRatings = true;
            return;
          }
          const parsed = JSON.parse(stored);
          if (parsed && typeof parsed === 'object') {
            Object.assign(ratings, parsed);
          }
        } catch (_error) {
          // Ignore malformed or blocked localStorage.
        }
        hasStoredRatings = true;

        try {
          const storedModes = localStorage.getItem(RATING_MODE_KEY);
          if (storedModes) {
            const parsedModes = JSON.parse(storedModes);
            if (parsedModes && typeof parsedModes === 'object') {
              Object.assign(ratingModes, parsedModes);
            }
          }
        } catch (_error) {
          // Ignore malformed or blocked localStorage.
        }
        hasStoredRatingModes = true;
      }

      function getPairNames(index) {
        const bwName = pairsBw[index];
        const colorName = pairsColor[index];
        return { bwName, colorName };
      }

      function setTileSources(tile, index) {
        const { bwName, colorName } = getPairNames(index);
        const highImage = tile.querySelector('.high');
        const colorImage = tile.querySelector('.color');
        const bwImage = tile.querySelector('.bw');
        if (!bwName || !colorName) {
          return false;
        }

        if (highImage) {
          highImage.src = `${HIGH_DIR}/${encodeURIComponent(colorName)}`;
          highImage.alt = `${bwName} high`;
        }
        if (colorImage) {
          colorImage.src = `${COLOR_DIR}/${encodeURIComponent(colorName)}`;
          colorImage.alt = `${bwName} color`;
        }
        if (bwImage) {
          bwImage.src = `${BW_DIR}/${encodeURIComponent(bwName)}`;
          bwImage.alt = `${bwName} black and white`;
        }

        tile.dataset.index = String(index);
        return true;
      }

      function attachOverlayInputHandlers(overlay) {
        overlay.addEventListener('click', (event) => {
          if (!['expanded', 'opening'].includes(zoomState.status)) {
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          if (zoomState.singleClickTimer) {
            window.clearTimeout(zoomState.singleClickTimer);
          }
          const delay = PLATFORM_IS_MAC ? 220 : 0;
          zoomState.singleClickTimer = window.setTimeout(() => {
            toggleBwMode(overlay);
            zoomState.singleClickTimer = null;
          }, delay);
        });

        const onHighColorToggle = (event) => {
          if (!['expanded', 'opening'].includes(zoomState.status)) {
            return;
          }
          if (zoomState.singleClickTimer) {
            window.clearTimeout(zoomState.singleClickTimer);
            zoomState.singleClickTimer = null;
          }
          event.preventDefault();
          event.stopPropagation();
          toggleHighColorMode(overlay);
        };

        const onHighColorMouseDown = (event) => {
          if (event.button !== 2) {
            return;
          }
          onHighColorToggle(event);
        };

        overlay.addEventListener('mousedown', onHighColorMouseDown);
        overlay.addEventListener('auxclick', onHighColorToggle);
        overlay.addEventListener('contextmenu', onHighColorToggle);
        if (PLATFORM_IS_MAC) {
          overlay.addEventListener('dblclick', onHighColorToggle);
        }
      }

      function applyRatingToTile(tile, index) {
        const rating = getRating(index);
        tile.classList.remove('rated-down', 'rated-down-high', 'rated-down-color');

        if (rating === 'down') {
          const mode = getStoredRatingMode(index);
          tile.classList.add('rated-down');
          tile.classList.add(mode === 'color' ? 'rated-down-color' : 'rated-down-high');
          return;
        }
      }

      function queueNavigation(direction) {
        if (direction !== -1 && direction !== 1) {
          return;
        }
        zoomState.queuedNavigation.push(direction);
      }

      function flushQueuedNavigation() {
        if (!['expanded', 'opening'].includes(zoomState.status) || zoomState.isNavigating || zoomState.isModeFading) {
          return;
        }
        const direction = zoomState.queuedNavigation.shift();
        if (direction !== -1 && direction !== 1) {
          return;
        }
        navigateToPhoto(direction);
      }

      function syncRatingForIndex(index) {
        const nodes = document.querySelectorAll(`.tile[data-index="${index}"], .tile-overlay[data-index="${index}"]`);
        nodes.forEach((node) => {
          applyRatingToTile(node, index);
        });
      }

      function updateRatingSummary() {
        if (!ratingSummary) {
          return;
        }

        let up = 0;
        let down = 0;
        let total = 0;
        const keys = Object.keys(ratings);
        for (const key of keys) {
          if (!key.startsWith(`${RATING_SCOPE}::`)) {
            continue;
          }
          const value = ratings[key];
          if (value === 'up') {
            up += 1;
          } else if (value === 'down') {
            down += 1;
          }
        }
        for (let i = 0; i < pairsBw.length; i++) {
          const key = ratingKey(i);
          if (key in ratings) {
            total += 1;
          }
        }
        ratingSummary.textContent = `Thumbs: 👍 ${up} / 👎 ${down} (${total} rated)`;
      }

      function setRating(index, value) {
        const nextValue = normalizeRatingValue(value);
        if (index < 0 || !Number.isFinite(index)) {
          return;
        }
        const key = ratingKey(index);
        const current = ratings[key];
        if (nextValue === null) {
          if (current !== undefined) {
            delete ratings[key];
            clearStoredRatingMode(index);
          }
        } else if (current === nextValue) {
          delete ratings[key];
          clearStoredRatingMode(index);
        } else {
          ratings[key] = nextValue;
          if (nextValue === 'down') {
            setStoredRatingMode(index, getActiveRatingMode(index));
          } else {
            clearStoredRatingMode(index);
          }
        }

        syncRatingForIndex(index);
        updateRatingSummary();
        persistRatings();
        persistRatingModes();
      }

      function getActiveIndexForRating() {
        if (zoomState.status === 'expanded' && zoomState.index >= 0) {
          return zoomState.index;
        }
        if (zoomState.selectedIndex >= 0) {
          return zoomState.selectedIndex;
        }

        const focusedTile = document.activeElement?.closest?.('.tile');
        if (focusedTile && focusedTile.dataset.index) {
          const focused = Number(focusedTile.dataset.index);
          if (Number.isFinite(focused)) {
            return focused;
          }
        }
        return -1;
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
        if (zoomState.singleClickTimer) {
          window.clearTimeout(zoomState.singleClickTimer);
        }
        if (zoomState.navigationTimer) {
          window.clearTimeout(zoomState.navigationTimer);
        }
        if (zoomState.modeFadeImage && zoomState.modeFadeHandler) {
          zoomState.modeFadeImage.removeEventListener('transitionend', zoomState.modeFadeHandler);
        }
        zoomState.sourceTile = null;
        zoomState.overlayTile = null;
        zoomState.backdrop = null;
        zoomState.startRect = null;
        zoomState.index = -1;
        zoomState.mode = 'bw';
        zoomState.nonBwMode = 'high';
        zoomState.openTimer = null;
        zoomState.closeTimer = null;
        zoomState.singleClickTimer = null;
        zoomState.navigationTimer = null;
        zoomState.isNavigating = false;
        zoomState.queuedNavigation = [];
        zoomState.isModeFading = false;
        zoomState.modeFadeImage = null;
        zoomState.modeFadeHandler = null;
        zoomState.status = 'idle';
      }

      function closeZoom() {
        if (!['opening', 'expanded'].includes(zoomState.status)) {
          return;
        }

        const overlayNodes = zoomState.backdrop ? zoomState.backdrop.querySelectorAll('.tile-overlay') : [];
        let overlayTile = zoomState.overlayTile;
        let sourceTile = zoomState.sourceTile;
        const startRect = zoomState.startRect;

        if (overlayNodes.length > 1) {
          overlayTile = overlayNodes[overlayNodes.length - 1];
          sourceTile = overlayTile ? overlayTile : sourceTile;
          zoomState.overlayTile = overlayTile;
          zoomState.sourceTile = sourceTile || zoomState.sourceTile;
        }
        if (zoomState.overlayTile && zoomState.backdrop) {
          const leftoverOverlays = zoomState.backdrop.querySelectorAll('.tile-overlay');
          leftoverOverlays.forEach((overlay) => {
            if (overlay !== zoomState.overlayTile) {
              overlay.remove();
            }
          });
        }

        if (!overlayTile || !startRect || !sourceTile) {
          cleanupZoom();
          return;
        }

        zoomState.status = 'closing';
        if (zoomState.openTimer) {
          window.clearTimeout(zoomState.openTimer);
          zoomState.openTimer = null;
        }
        if (zoomState.singleClickTimer) {
          window.clearTimeout(zoomState.singleClickTimer);
          zoomState.singleClickTimer = null;
        }
        overlayTile.style.transform = 'translateX(0px)';
        overlayTile.style.top = `${startRect.top}px`;
        overlayTile.style.left = `${startRect.left}px`;
        overlayTile.style.width = `${startRect.width}px`;
        overlayTile.style.height = `${startRect.height}px`;
        applyTileMode(overlayTile, 'bw');

        let done = false;
        const finalize = () => {
          if (done) {
            return;
          }
          done = true;
          applyTileMode(sourceTile, 'bw');
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

      function navigateToPhoto(direction) {
        if (!['expanded', 'opening'].includes(zoomState.status) || !Number.isInteger(direction)) {
          return;
        }
        if (zoomState.isNavigating || zoomState.isModeFading || zoomState.openTimer) {
          queueNavigation(direction);
          return;
        }

        const total = pairsBw.length;
        if (total < 2) {
          return;
        }

        const nextIndex = ((zoomState.index + direction) + total) % total;
        if (nextIndex === zoomState.index) {
          return;
        }

        const sourceTile = gallery.querySelector(`.tile[data-index="${nextIndex}"]`);
        if (!sourceTile) {
          return;
        }

        const sourceFrame = sourceTile.querySelector('.frame');
        if (!sourceFrame) {
          return;
        }
        const sourceRect = sourceFrame.getBoundingClientRect();
        if (!sourceRect.width || !sourceRect.height) {
          return;
        }

        if (!zoomState.overlayTile || !zoomState.backdrop) {
          return;
        }

        const incoming = zoomState.overlayTile.cloneNode(true);
        if (!setTileSources(incoming, nextIndex)) {
          return;
        }
        if (!incoming.querySelector('.frame')) {
          return;
        }

        if (zoomState.singleClickTimer) {
          window.clearTimeout(zoomState.singleClickTimer);
          zoomState.singleClickTimer = null;
        }
        if (zoomState.navigationTimer) {
          window.clearTimeout(zoomState.navigationTimer);
          zoomState.navigationTimer = null;
        }

        const centered = getCenteredRect(pairRatios[nextIndex] || pairRatios[zoomState.index] || DEFAULT_ASPECT);
        const restoreModeAfterNavigation = (zoomState.mode === 'high' || zoomState.mode === 'color')
          ? zoomState.mode
          : (zoomState.nonBwMode || getStoredNonBwMode(zoomState.index) || 'high');
        const startMode = 'bw';
        const travelDistance = Math.max(window.innerWidth, 560) * 1.08;

        incoming.className = 'tile-overlay';
        incoming.dataset.zoomed = 'true';
        incoming.dataset.index = String(nextIndex);
        incoming.style.top = `${centered.top}px`;
        incoming.style.left = `${centered.left}px`;
        incoming.style.width = `${centered.width}px`;
        incoming.style.height = `${centered.height}px`;
        incoming.style.opacity = '1';
        incoming.style.transform = `translateX(${direction > 0 ? travelDistance : -travelDistance}px)`;
        applyTileMode(incoming, startMode);
        if (pairRatios[nextIndex]) {
          incoming.style.setProperty('--frame-aspect-ratio', String(pairRatios[nextIndex]));
        } else if (pairRatios[zoomState.index]) {
          incoming.style.setProperty('--frame-aspect-ratio', String(pairRatios[zoomState.index]));
        } else {
          incoming.style.setProperty('--frame-aspect-ratio', String(DEFAULT_ASPECT));
        }
        applyRatingToTile(incoming, nextIndex);
        attachOverlayInputHandlers(incoming);

        const previous = zoomState.overlayTile;
        previous.style.transform = 'translateX(0px)';
        zoomState.status = 'opening';
        zoomState.backdrop.appendChild(incoming);
        incoming.offsetWidth;

        zoomState.isNavigating = true;
        window.requestAnimationFrame(() => {
          incoming.offsetWidth;
          previous.style.transform = `translateX(${direction > 0 ? -travelDistance : travelDistance}px)`;
          incoming.style.transform = 'translateX(0px)';
        });

        let done = false;
        const finish = (evt) => {
          if (done) {
            return;
          }
          if (evt && evt.target && (evt.target !== incoming || evt.propertyName !== 'transform')) {
            return;
          }
          done = true;
          incoming.removeEventListener('transitionend', finish);
          zoomState.isNavigating = false;

          if (zoomState.navigationTimer) {
            window.clearTimeout(zoomState.navigationTimer);
            zoomState.navigationTimer = null;
          }

          previous.remove();

          incoming.style.transform = 'translateX(0px)';
          incoming.className = 'tile-overlay';
          zoomState.overlayTile = incoming;
          zoomState.sourceTile = sourceTile;
          zoomState.startRect = {
            top: sourceRect.top,
            left: sourceRect.left,
            width: sourceRect.width,
            height: sourceRect.height
          };
          zoomState.index = nextIndex;
          zoomState.selectedIndex = nextIndex;
          zoomState.mode = startMode;
          zoomState.nonBwMode = restoreModeAfterNavigation;
          zoomState.status = 'expanded';

          if (restoreModeAfterNavigation) {
            window.requestAnimationFrame(() => {
              if (!zoomState.overlayTile || zoomState.index !== nextIndex || zoomState.status !== 'expanded') {
                return;
              }
              applyZoomMode(zoomState.overlayTile, restoreModeAfterNavigation);
              setStoredNonBwMode(nextIndex, restoreModeAfterNavigation);
              persistRatingModes();
            });
            return;
          }
          persistRatingModes();
          flushQueuedNavigation();
        };

        incoming.addEventListener('transitionend', finish);
        zoomState.navigationTimer = window.setTimeout(() => {
          finish({ target: incoming, propertyName: 'transform' });
        }, OPEN_ANIMATION_MS + 40);
      }

      function openZoom(sourceTile, index) {
        if (zoomState.status !== 'idle' || !sourceTile) {
          return;
        }
        if (zoomState.navigationTimer) {
          window.clearTimeout(zoomState.navigationTimer);
          zoomState.navigationTimer = null;
        }
        if (zoomState.modeFadeImage && zoomState.modeFadeHandler) {
          zoomState.modeFadeImage.removeEventListener('transitionend', zoomState.modeFadeHandler);
        }
        zoomState.modeFadeImage = null;
        zoomState.modeFadeHandler = null;
        zoomState.isNavigating = false;
        zoomState.queuedNavigation = [];
        zoomState.isModeFading = false;

        const sourceFrame = sourceTile.querySelector('.frame');
        const sourceRect = sourceFrame.getBoundingClientRect();
        if (!sourceRect.width || !sourceRect.height) {
          applyTileMode(sourceTile, 'bw');
          return;
        }

        const overlay = sourceTile.cloneNode(true);
        overlay.className = 'tile-overlay';
        overlay.dataset.zoomed = 'true';
        overlay.dataset.index = String(index);
        overlay.style.top = `${sourceRect.top}px`;
        overlay.style.left = `${sourceRect.left}px`;
        overlay.style.width = `${sourceRect.width}px`;
        overlay.style.height = `${sourceRect.height}px`;
        applyTileMode(overlay, 'bw');
        applyRatingToTile(overlay, index);

        const overlayCaption = overlay.querySelector('.caption');
        if (overlayCaption) {
          overlayCaption.style.display = 'none';
        }

        attachOverlayInputHandlers(overlay);

        const backdrop = document.createElement('div');
        backdrop.className = 'gallery-backdrop';
        backdrop.appendChild(overlay);
        document.body.appendChild(backdrop);
        requestAnimationFrame(() => {
          backdrop.classList.add('active');
          requestAnimationFrame(() => {
            const centered = getCenteredRect(pairRatios[index] || DEFAULT_ASPECT);
            overlay.style.top = `${centered.top}px`;
            overlay.style.left = `${centered.left}px`;
            overlay.style.width = `${centered.width}px`;
            overlay.style.height = `${centered.height}px`;
            overlay.offsetWidth;
          });
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
        zoomState.mode = 'bw';
        zoomState.nonBwMode = getStoredNonBwMode(index);
        zoomState.selectedIndex = index;

        backdrop.addEventListener('click', (event) => {
          if (event.target !== backdrop) {
            return;
          }
          event.preventDefault();
          event.stopPropagation();
          closeZoom();
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
          zoomState.status = 'expanded';
          applyZoomMode(overlay, zoomState.nonBwMode || 'high');
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

      function buildTile(index) {
        const bwName = pairsBw[index];
        const colorName = pairsColor[index];

        const tile = document.createElement('button');
        tile.type = 'button';
        tile.className = 'tile';
        tile.dataset.index = String(index);
        tile.dataset.mode = 'bw';
        tile.setAttribute('aria-label', `Reveal color version of ${bwName}`);

        const frame = document.createElement('div');
        frame.className = 'frame';

        const highSrc = `${HIGH_DIR}/${encodeURIComponent(colorName)}`;
        const colorSrc = `${COLOR_DIR}/${encodeURIComponent(colorName)}`;
        const bwSrc = `${BW_DIR}/${encodeURIComponent(bwName)}`;

        const high = new Image();
        high.className = 'high';
        high.loading = 'lazy';
        high.decoding = 'async';
        high.alt = `${bwName} high`;
        high.src = highSrc;

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

        high.addEventListener('load', () => {
          setTileAspect(index, tile, high.naturalWidth, high.naturalHeight);
          logImageStatus('High', colorName, highSrc, true);
        });
        high.addEventListener('error', () => { logImageStatus('High', colorName, highSrc, false); });
        color.addEventListener('load', () => {
          setTileAspect(index, tile, color.naturalWidth, color.naturalHeight);
          logImageStatus('Color', colorName, colorSrc, true);
        });
        color.addEventListener('error', () => { logImageStatus('Color', colorName, colorSrc, false); });
        bw.addEventListener('load', () => {
          setTileAspect(index, tile, bw.naturalWidth, bw.naturalHeight);
          logImageStatus('B/W', bwName, bwSrc, true);
        });
        bw.addEventListener('error', () => { logImageStatus('B/W', bwName, bwSrc, false); });

        frame.appendChild(high);
        frame.appendChild(color);
        frame.appendChild(bw);

        const caption = document.createElement('div');
        caption.className = 'caption';
        caption.textContent = bwName;

        tile.appendChild(frame);
        tile.appendChild(caption);

        applyTileMode(tile, 'bw');
        applyRatingToTile(tile, index);

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

          zoomState.selectedIndex = index;
          event.preventDefault();
          openZoom(tile, index);
        });

        return tile;
      }

      function onTileFocusIn(event) {
        const tile = event.target.closest('.tile');
        if (!tile || !tile.dataset || !tile.dataset.index) {
          return;
        }
        zoomState.selectedIndex = Number(tile.dataset.index);
      }

      if (shortcutHint) {
        shortcutHint.textContent = 'Shortcut keys: 1 (👍), 2 (👎), c (High/Color), ←/→ (prev/next), Esc (close)';
      }

      document.addEventListener('focusin', onTileFocusIn);

      window.addEventListener('keydown', (event) => {
        if (event.defaultPrevented) {
          return;
        }

        if (event.key === 'Escape') {
          if (!['expanded', 'opening'].includes(zoomState.status)) {
            return;
          }
          event.preventDefault();
          closeZoom();
          return;
        }

        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
          if (!['expanded', 'opening'].includes(zoomState.status)) {
            return;
          }
          event.preventDefault();
          navigateToPhoto(event.key === 'ArrowLeft' ? -1 : 1);
          return;
        }

        const key = String(event.key || '').toLowerCase();
        if (key !== '1' && key !== '2' && key !== 'c') {
          return;
        }

        if (key === 'c') {
          if (!zoomState.overlayTile || (zoomState.status !== 'expanded' && zoomState.status !== 'opening')) {
            return;
          }
          event.preventDefault();
          toggleHighColorMode(zoomState.overlayTile);
          return;
        }

        const index = getActiveIndexForRating();
        if (index < 0) {
          return;
        }

        const rating = event.key === '1' ? 'up' : 'down';
        event.preventDefault();
        setRating(index, rating);
      });

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
        debugToggle.textContent = debugPanel.style.display === 'none' ? 'Show logs' : 'Hide logs';
      });

      if (!pairsBw || pairsBw.length === 0) {
        const msg = 'No matching filenames were found.';
        if (count) {
          count.textContent = msg;
        }
        logEvent('error', msg);
      } else {
        const msg = `${pairsBw.length} matching pairs loaded.`;
        if (count) {
          count.textContent = msg;
        }
        logEvent('info', msg);
      }

      loadRatings();
      stats.total = pairsBw.length * STATS_LAYER_COUNT;
      logEvent('info', `Page loaded via ${location.protocol}`);

      for (let i = 0; i < pairsBw.length; i++) {
        const tile = buildTile(i);
        gallery.appendChild(tile);
        syncRatingForIndex(i);
      }

      if (gallery) {
        updateRatingSummary();
      }
