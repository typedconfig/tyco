// Simple spec version navigation
document.addEventListener('DOMContentLoaded', function () {
  var sel = document.getElementById('spec-version');
  if (!sel) return;
  sel.addEventListener('change', function (e) {
    var v = e.target.value;
    if (!v) return;
    // navigate to spec page for selected version.
    // If we're on a spec page (path contains '/spec/'), navigate to the sibling file
    // Otherwise, navigate to the site-level `spec/` folder.
    try {
      var path = window.location.pathname || '';
      var url;
      if (path.indexOf('/spec/') !== -1 || path.match(/\/spec\/$/)) {
        // we're already in spec folder; go to sibling file
        url = v + '.html';
      } else {
        // not in spec: go to spec/<version>.html relative to current page
        url = 'spec/' + v + '.html';
      }
      window.location.href = url;
    } catch (err) {
      // fallback
      window.location.href = 'spec/' + v + '.html';
    }
  });
});

/* Auto-scroll code blocks horizontally during selection when pointer is near edges.
   This keeps scrollbars hidden but allows the user to select long lines by dragging.
*/
document.addEventListener('DOMContentLoaded', function () {
  var active = { el: null, pointerDown: false };

  function findPreAncestor(node) {
    while (node && node !== document.body) {
      if (node.tagName && node.tagName.toLowerCase() === 'pre') return node;
      node = node.parentNode;
    }
    return null;
  }

  document.addEventListener('pointerdown', function (e) {
    var pre = findPreAncestor(e.target);
    if (pre) active.el = pre;
    active.pointerDown = true;
  });

  document.addEventListener('pointerup', function () { active.pointerDown = false; active.el = null; });

  document.addEventListener('pointermove', function (e) {
    if (!active.pointerDown || !active.el) return;
    try {
      var rect = active.el.getBoundingClientRect();
      var leftEdge = rect.left + 40; // px threshold
      var rightEdge = rect.right - 40;
      var speed = 8; // pixels per event
      if (e.clientX < leftEdge) {
        active.el.scrollLeft -= speed;
      } else if (e.clientX > rightEdge) {
        active.el.scrollLeft += speed;
      }
    } catch (err) {
      // ignore
    }
  }, {passive:true});
});

// Populate copyright year
document.addEventListener('DOMContentLoaded', function () {
  var el = document.getElementById('copyright-year');
  if (!el) return;
  var y = new Date().getFullYear();
  el.textContent = y;
});

// Scrollspy for spec pages: keep TOC item highlighted while scrolling
document.addEventListener('DOMContentLoaded', function () {
  var toc = document.querySelector('.spec-toc');
  if (!toc) return;

  var links = Array.from(toc.querySelectorAll('a'));
  var sections = links.map(function (a) {
    var id = a.getAttribute('href');
    if (!id || id.indexOf('#') !== 0) return null;
    return document.querySelector(id);
  });

  // Ensure the spec-wrap sits flush under the fixed banner on first render.
  // Some spec pages add body/container padding which can introduce a visible
  // gap until the user scrolls; compute the current top and immediately
  // nudge the `.spec-wrap` up so its top aligns with the banner bottom.
  (function alignSpecWrapToBanner(){
    var wrap = document.querySelector('.spec-wrap');
    if (!wrap) return;
    var bannerHeight = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--banner-height')) || 44;
    // current distance from the viewport top to the wrap
    var rect = wrap.getBoundingClientRect();
    var currentTop = rect.top;
    var delta = currentTop - bannerHeight;
    if (delta > 0) {
      // set inline style to immediately cancel the extra spacing
      wrap.style.top = '-' + delta + 'px';
    }
    // Also ensure the spec content has enough top padding (banner + container padding)
    var content = document.querySelector('.spec-content');
    if (content) {
      var specContainerPadding = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--spec-container-padding')) || 1.25;
      // compute desired padding in px: bannerHeight + specContainerPadding (specContainerPadding is in rem-like units defined by CSS var; convert by multiplying the root font size)
      var rootFontSize = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      var specPaddingPx = Math.round(bannerHeight + (specContainerPadding * rootFontSize));
      content.style.paddingTop = specPaddingPx + 'px';
    }
  })();

  // helper to clear and set active class
  function setActive(index) {
    links.forEach(function (l, i) {
      if (i === index) l.classList.add('active');
      else l.classList.remove('active');
    });
  }

  // Throttled scroll handler
  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    window.requestAnimationFrame(function () {
      var fromTop = window.scrollY + (parseInt(getComputedStyle(document.documentElement).getPropertyValue('--banner-height')) || 44) + 8;
      var current = -1;
      sections.forEach(function (sec, i) {
        if (!sec) return;
        if (sec.offsetTop <= fromTop) current = i;
      });
      if (current >= 0) setActive(current);
      ticking = false;
    });
  }

  // initial highlight
  onScroll();
  window.addEventListener('scroll', onScroll, {passive:true});

  // smooth scroll behavior for TOC links
  links.forEach(function (a) {
    a.addEventListener('click', function (e) {
      var href = a.getAttribute('href');
      if (!href || href.indexOf('#') !== 0) return;
      var target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      var headerOffset = (parseInt(getComputedStyle(document.documentElement).getPropertyValue('--banner-height')) || 44) + 8;
      var elementPosition = target.getBoundingClientRect().top + window.scrollY;
      var offsetPosition = elementPosition - headerOffset;
      window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
      // update hash without jumping
      if (history.replaceState) {
        history.replaceState(null, '', href);
      } else {
        // fallback: set after a small timeout
        setTimeout(function () { location.hash = href; }, 500);
      }
    });
  });

  // If page loaded with a hash, scroll to it accounting for the banner
  if (location.hash) {
    var initialTarget = document.querySelector(location.hash);
    if (initialTarget) {
      setTimeout(function () {
        var headerOffset = (parseInt(getComputedStyle(document.documentElement).getPropertyValue('--banner-height')) || 44) + 8;
        var elementPosition = initialTarget.getBoundingClientRect().top + window.scrollY;
        var offsetPosition = elementPosition - headerOffset;
        window.scrollTo({ top: offsetPosition });
      }, 40);
    }
  }

});
