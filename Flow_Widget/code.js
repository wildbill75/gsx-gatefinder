function initGSXGateFinder() {
    const appWindow = document.getElementById('app');
    const dragHeader = document.getElementById('drag-header');
    const btnClose = document.getElementById('btn-close');
    const btnImport = document.getElementById('btn-import');
    
    if (!btnImport || !appWindow || !dragHeader || !btnClose) {
        // Elements not yet injected by Flow, wait and retry
        setTimeout(initGSXGateFinder, 100);
        return;
    }

    // Force display in case it was closed previously
    appWindow.style.display = 'block';

    // --- Window Drag Logic ---
    let isDragging = false;
    let offsetX, offsetY;

    dragHeader.addEventListener('mousedown', (e) => {
        isDragging = true;
        offsetX = e.clientX - appWindow.offsetLeft;
        offsetY = e.clientY - appWindow.offsetTop;
    });

    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        appWindow.style.left = (e.clientX - offsetX) + 'px';
        appWindow.style.top = (e.clientY - offsetY) + 'px';
    });

    document.addEventListener('mouseup', () => {
        isDragging = false;
    });

    // --- Close Logic ---
    btnClose.addEventListener('click', () => {
        appWindow.style.display = 'none';
    });

    const resultsContainer = document.getElementById('results-container');
    const errorMsg = document.getElementById('error-message');
    const airportsList = document.getElementById('airports-list');
    const statusIndicator = document.getElementById('server-status');
    const tplAirport = document.getElementById('tpl-airport');

    const elAircraft = document.getElementById('res-aircraft');
    const elAirline = document.getElementById('res-airline');

    btnImport.addEventListener('click', () => {
        resultsContainer.classList.add('hidden');
        errorMsg.classList.add('hidden');
        airportsList.innerHTML = '';
        btnImport.innerHTML = 'Loading...';

        fetch('http://127.0.0.1:8420/api/simbrief')
            .then(res => {
                statusIndicator.className = 'status-indicator online';
                return res.json();
            })
            .then(data => {
                btnImport.innerHTML = 'Refresh SimBrief';
                if (data.error) {
                    errorMsg.textContent = data.error;
                    errorMsg.classList.remove('hidden');
                    return;
                }

                elAircraft.textContent = data.aircraft || 'UNK';
                elAirline.textContent = data.airline || 'UNK';

                if (data.departure) renderAirport('🛫 DEP', data.departure);
                if (data.arrival) renderAirport('🛬 ARR', data.arrival);
                if (data.alternate) renderAirport('✈ ALT', data.alternate);

                resultsContainer.classList.remove('hidden');
            })
            .catch(err => {
                statusIndicator.className = 'status-indicator offline';
                btnImport.innerHTML = 'Import SimBrief';
                errorMsg.textContent = "Could not connect to Desktop App.";
                errorMsg.classList.remove('hidden');
            });
    });

    function renderAirport(typeLabel, apData) {
        const clone = tplAirport.content.cloneNode(true);
        clone.querySelector('.ap-type').textContent = typeLabel;
        clone.querySelector('.ap-icao').textContent = apData.icao || '????';

        const errEl = clone.querySelector('.airport-error');
        const gatesContainer = clone.querySelector('.gates-container');

        if (apData.error) {
            errEl.textContent = apData.error;
            errEl.classList.remove('hidden');
        } else if (apData.gates) {
            for (const [termName, gates] of Object.entries(apData.gates)) {
                const termGroup = document.createElement('div');
                termGroup.className = 'terminal-group';
                
                const termTitle = document.createElement('div');
                termTitle.className = 'terminal-name';
                termTitle.textContent = termName;
                termGroup.appendChild(termTitle);

                const gateList = document.createElement('div');
                gateList.className = 'gates-list';
                
                gates.forEach(g => {
                    const pill = document.createElement('span');
                    pill.className = 'gate-pill';
                    pill.textContent = g;
                    gateList.appendChild(pill);
                });

                termGroup.appendChild(gateList);
                gatesContainer.appendChild(termGroup);
            }
        }
        airportsList.appendChild(clone);
    }
}

// Start the loop
initGSXGateFinder();
