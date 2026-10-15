(() => {
    function thumbGeometry(viewport, content, track, position) {
        const range = Math.max(0, content - viewport);
        const size = Math.min(track, Math.max(24, track * viewport / content));
        const travel = Math.max(0, track - size);
        return {range, size, travel, offset: range ? travel * Math.max(0, Math.min(range, position)) / range : 0};
    }
    if (typeof module !== "undefined") module.exports = {thumbGeometry};
    if (typeof document === "undefined" || !window.ResizeObserver
        || window.matchMedia("(forced-colors: active)").matches) return;

    const root = document.scrollingElement;
    const host = document.createElement("div");
    host.className = "overlay-scrollbars";
    host.setAttribute("aria-hidden", "true");
    document.body.appendChild(host);
    const entries = new Map();
    let frame = 0;
    let pointerTarget = null;
    let dragging = null;
    const resizeObserver = new ResizeObserver(schedule);

    function schedule() {
        if (!frame) frame = requestAnimationFrame(render);
    }
    function register(element) {
        if (!(element instanceof Element) || element.closest(".overlay-scrollbars")) return;
        const style = getComputedStyle(element);
        if (element !== root && !/auto|scroll/.test(`${style.overflowX} ${style.overflowY}`)) return;
        if (entries.has(element)) return;
        const bars = ["y", "x"].map(axis => {
            const track = document.createElement("div");
            track.className = `overlay-scrollbar axis-${axis}`;
            const thumb = document.createElement("div");
            thumb.className = "overlay-scrollbar-thumb";
            track.appendChild(thumb);
            host.appendChild(track);
            const bar = {axis, track, thumb, geometry: null};
            track.addEventListener("wheel", event => {
                if (!bar.geometry?.range) return;
                event.preventDefault();
                const delta = axis === "y" ? event.deltaY : event.deltaX || event.deltaY;
                const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2
                    ? (axis === "y" ? element.clientHeight : element.clientWidth) : 1;
                element[axis === "y" ? "scrollTop" : "scrollLeft"] += delta * unit;
            }, {passive: false});
            track.addEventListener("pointerdown", event => {
                if (event.button !== 0 || !bar.geometry?.range) return;
                event.preventDefault();
                event.stopPropagation();
                const rect = track.getBoundingClientRect();
                const coordinate = axis === "y" ? event.clientY : event.clientX;
                const start = axis === "y" ? rect.top : rect.left;
                const property = axis === "y" ? "scrollTop" : "scrollLeft";
                if (event.target !== thumb) {
                    element[property] = Math.max(0, Math.min(bar.geometry.range,
                        (coordinate - start - bar.geometry.size / 2) / (bar.geometry.travel || 1) * bar.geometry.range));
                }
                dragging = {element, bar, coordinate, position: element[property], property, pointerId: event.pointerId};
                track.setPointerCapture(event.pointerId);
                schedule();
            });
            track.addEventListener("pointermove", event => {
                if (!dragging || dragging.bar !== bar || dragging.pointerId !== event.pointerId) return;
                const coordinate = axis === "y" ? event.clientY : event.clientX;
                element[dragging.property] = dragging.position + (coordinate - dragging.coordinate)
                    * bar.geometry.range / (bar.geometry.travel || 1);
            });
            const endDrag = () => { dragging = null; schedule(); };
            track.addEventListener("pointerup", endDrag);
            track.addEventListener("pointercancel", endDrag);
            track.addEventListener("lostpointercapture", endDrag);
            return bar;
        });
        entries.set(element, {bars, activeUntil: 0});
        resizeObserver.observe(element);
    }
    function scan(node) {
        register(node);
        node.querySelectorAll?.("*").forEach(register);
    }
    function visibleRect(element) {
        let rect = element === root
            ? {left: 0, top: 0, right: window.innerWidth, bottom: window.innerHeight}
            : element.getBoundingClientRect();
        let {left, top, right, bottom} = rect;
        if (getComputedStyle(element).visibility === "hidden" || element.closest("[hidden]")) return null;
        for (let parent = element.parentElement; parent && element !== root; parent = parent.parentElement) {
            const style = getComputedStyle(parent);
            if (style.visibility === "hidden" || Number(style.opacity) === 0) return null;
            const bounds = parent.getBoundingClientRect();
            if (/hidden|clip|auto|scroll/.test(style.overflowX)) {
                left = Math.max(left, bounds.left); right = Math.min(right, bounds.right);
            }
            if (/hidden|clip|auto|scroll/.test(style.overflowY)) {
                top = Math.max(top, bounds.top); bottom = Math.min(bottom, bounds.bottom);
            }
        }
        left = Math.max(0, left); top = Math.max(0, top);
        right = Math.min(window.innerWidth, right); bottom = Math.min(window.innerHeight, bottom);
        return right > left && bottom > top ? {left, top, right, bottom} : null;
    }
    function render() {
        frame = 0;
        const now = performance.now();
        for (const [element, entry] of entries) {
            if (!element.isConnected) {
                entry.bars.forEach(bar => bar.track.remove());
                resizeObserver.unobserve(element);
                entries.delete(element);
                continue;
            }
            const rect = visibleRect(element);
            const visible = element === root || element.contains(pointerTarget) || element.contains(document.activeElement)
                || entry.activeUntil > now || dragging?.element === element;
            entry.bars.forEach(bar => {
                const vertical = bar.axis === "y";
                const content = vertical ? element.scrollHeight : element.scrollWidth;
                const viewport = vertical ? element.clientHeight : element.clientWidth;
                const length = rect ? (vertical ? rect.bottom - rect.top : rect.right - rect.left) - 4 : 0;
                const overflow = element === root || /auto|scroll/.test(getComputedStyle(element)[vertical ? "overflowY" : "overflowX"]);
                bar.track.hidden = !rect || !overflow || content <= viewport + 1 || length <= 0;
                if (bar.track.hidden) return;
                bar.geometry = thumbGeometry(viewport, content, length, element[vertical ? "scrollTop" : "scrollLeft"]);
                Object.assign(bar.track.style, vertical
                    ? {top: `${rect.top + 2}px`, left: `${rect.right - 9}px`, height: `${length}px`}
                    : {top: `${rect.bottom - 9}px`, left: `${rect.left + 2}px`, width: `${length}px`});
                bar.track.classList.toggle("is-visible", visible);
                Object.assign(bar.thumb.style, vertical
                    ? {height: `${bar.geometry.size}px`, transform: `translateY(${bar.geometry.offset}px)`}
                    : {width: `${bar.geometry.size}px`, transform: `translateX(${bar.geometry.offset}px)`});
            });
        }
    }
    scan(document.documentElement);
    new MutationObserver(records => {
        let changed = false;
        records.forEach(record => {
            if (record.target instanceof Element && record.target.closest(".overlay-scrollbars")) return;
            changed = true;
            if (record.type === "childList") record.addedNodes.forEach(scan);
            else register(record.target);
        });
        if (changed) schedule();
    }).observe(document.body, {subtree: true, childList: true, attributes: true,
        attributeFilter: ["class", "style", "hidden", "open"]});
    document.addEventListener("pointerover", event => {
        if (!host.contains(event.target)) pointerTarget = event.target;
        schedule();
    });
    document.addEventListener("pointerout", event => {
        if (!host.contains(event.relatedTarget)) pointerTarget = event.relatedTarget;
        schedule();
    });
    document.addEventListener("focusin", schedule);
    document.addEventListener("focusout", schedule);
    document.addEventListener("scroll", event => {
        const entry = entries.get(event.target === document ? root : event.target);
        if (entry) {
            entry.activeUntil = performance.now() + 1000;
            setTimeout(schedule, 1050);
        }
        schedule();
    }, true);
    window.addEventListener("resize", schedule);
    document.addEventListener("transitionend", schedule, true);
    document.addEventListener("dashboard-carousel-card-changed", schedule);
    document.documentElement.classList.add("has-overlay-scrollbars");
    schedule();
})();
