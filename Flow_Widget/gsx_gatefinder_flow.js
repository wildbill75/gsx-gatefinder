/*
  //42 Flow Widget for GSX Gate Finder
  Instructions:
  1. Create a new Script widget in your Flow wheel.
  2. Paste this code into the Script editor.
  3. Ensure your GSX GateFinder.exe is running in the background.
*/

function run() {
    // We create a temporary overlay/alert in Flow, or just fetch and log for now.
    // Flow provides specific UI APIs depending on version, but the simplest is to just output the result to a small text box or use a standard JS alert if supported.
    
    fetch('http://127.0.0.1:8420/api/simbrief')
    .then(response => response.json())
    .then(data => {
        if(data.error) {
            console.log("GSX Gate Finder Error: " + data.error);
            return;
        }
        
        let output = "✈ " + data.aircraft + " | 🏢 " + data.airline + "\n\n";
        
        if(data.departure && !data.departure.error) {
            output += "🛫 DEP (" + data.departure.icao + "): \n";
            for(let term in data.departure.gates) {
                output += "📍 " + term + ": " + data.departure.gates[term].join(', ') + "\n";
            }
        }
        
        if(data.arrival && !data.arrival.error) {
            output += "\n🛬 ARR (" + data.arrival.icao + "): \n";
            for(let term in data.arrival.gates) {
                output += "📍 " + term + ": " + data.arrival.gates[term].join(', ') + "\n";
            }
        }
        
        // Flow's notify or alert system can be used here. For now, logging to console.
        // If Flow has a built-in alert/notify, we could use that.
        console.log(output);
        
        // Fallback for visual display if Flow doesn't trap window.alert
        if(typeof window.alert === 'function') {
            window.alert("GSX GATE FINDER\n\n" + output);
        }
    })
    .catch(err => {
        console.log("GSX Gate Finder Server Offline. Ensure the desktop app is running.");
    });
}

run();
