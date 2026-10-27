/* Mounts the loader from BRAND_CONFIG, plays once, then hard-cuts (removes node, no fade).
   API: LoomiLoader.mount({minMs, theme, size}) -> {ready(), finish()}.
   Cut happens at max(animation end, app ready()). Fires window event "loomi:loader-done". */
(function(){
  var B=window.BRAND_CONFIG;
  window.LoomiLoader={mount:function(o){
    o=o||{};var dur=o.durationMs||1200,el=document.createElement('div');
    el.className='lm-loader';el.setAttribute('role','status');el.setAttribute('aria-busy','true');
    el.setAttribute('aria-label','Loading '+B.name);
    if(o.theme)el.dataset.theme=o.theme;
    if(o.size)el.style.setProperty('--lm-size',o.size+'px');
    el.style.setProperty('--lm-dur',dur+'ms');
    el.innerHTML='<div class="lm-float">'+B.logoSvg+'</div>';
    document.body.appendChild(el);
    var played=false,isReady=o.waitForReady?false:true,done=false;
    function finish(){if(done)return;done=true;el.remove();
      window.dispatchEvent(new CustomEvent('loomi:loader-done'));}
    function check(){if(played&&isReady)finish();}
    var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
    if(!o.manual)setTimeout(function(){played=true;check();},reduce?Math.min(dur,400):dur);
    return {el:el,ready:function(){isReady=true;check();},finish:finish};
  }};
})();
