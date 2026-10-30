/* Lineage read-only demo: switch off the parts that need the local server. */
(function(){
  const msg = 'The terminal runs Claude Code on your own machine. Run it yourself with "make demo".';
  window.openDock = function(open){ if(open) demoNote(msg); };
  window.sendToTerminal = function(){ demoNote(msg); };
  window.runJob = async function(stage, onStep, onDone, onError){ demoNote('Pipeline steps run on your own machine ("make demo").'); onError && onError('read-only demo'); };
  document.addEventListener('DOMContentLoaded', ()=>{
    const bar = document.createElement('div');
    bar.className = 'demo-bar';
    bar.innerHTML = '<span><b>Read-only demo</b> of an invented family, the Calders. Nothing you change is saved.</span>'
      + '<span>Run it yourself: <code>make demo</code> · <a href="../">About Lineage</a> · <a href="../install/">Install</a></span>';
    document.body.prepend(bar);
  });
})();
