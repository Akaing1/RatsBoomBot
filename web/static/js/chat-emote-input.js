(() => {
    // Keep the form's textarea as the plain-text transport; this adapter exposes
    // its familiar editing API while the visible editor contains atomic emotes.
    window.createChatEmoteInput = ({input: source, getEmotes, enabled = () => true, onLimit = () => {}}) => {
        const editor = document.createElement('div');
        editor.className = 'chat-rich-input'; editor.contentEditable = 'true';
        editor.setAttribute('role', 'textbox'); editor.setAttribute('aria-multiline', 'true');
        editor.setAttribute('aria-label', source.getAttribute('aria-label') || 'Message');
        editor.setAttribute('aria-placeholder', source.placeholder);
        for (const name of ['aria-describedby', 'aria-keyshortcuts']) {
            if (source.hasAttribute(name)) editor.setAttribute(name, source.getAttribute(name));
        }
        const original = {hidden: source.hidden, required: source.required};
        if (source.required) editor.setAttribute('aria-required', 'true');
        source.hidden = true; source.required = false;
        source.dataset.emoteSource = 'true';
        source.insertAdjacentElement('afterend', editor);
        let active = true, composing = false, catalogSource = null, catalog = new Map();
        let renderedText = null, renderedEnabled = null, renderedCatalog = null;
        let selection = {start: source.value.length, end: source.value.length};
        const listeners = [], undo = [], redo = [];
        const length = node => {
            if (node.nodeType === 3) return node.data.length;
            if (node.dataset?.emoteName) return node.dataset.emoteName.length;
            if (node.nodeName === 'BR') return node.dataset.tail ? 0 : 1;
            return [...node.childNodes].reduce((sum, child) => sum + length(child), 0);
        };
        const text = node => {
            if (node.nodeType === 3) return node.data;
            if (node.dataset?.emoteName) return node.dataset.emoteName;
            if (node.nodeName === 'BR') return node.dataset.tail ? '' : '\n';
            return [...node.childNodes].map(text).join('');
        };
        function offset(container, index) {
            let total = 0, found = false;
            function visit(node) {
                if (found) return;
                if (node === container) {
                    total += node.nodeType === 3 ? index : [...node.childNodes].slice(0, index).reduce((sum, child) => sum + length(child), 0);
                    found = true;
                } else if (node.nodeType === 3 || node.dataset?.emoteName || node.nodeName === 'BR') total += length(node);
                else [...node.childNodes].forEach(visit);
            }
            visit(editor);
            return total;
        }
        function readSelection() {
            const current = window.getSelection();
            if (current?.rangeCount && editor.contains(current.anchorNode) && editor.contains(current.focusNode)) {
                const range = current.getRangeAt(0);
                selection = {start: offset(range.startContainer, range.startOffset), end: offset(range.endContainer, range.endOffset)};
            }
            return selection;
        }
        function point(index) {
            let remaining = index;
            function find(node) {
                if (node.nodeType === 3 && remaining <= node.data.length) return [node, remaining];
                if (node.dataset?.emoteName || node.nodeName === 'BR') {
                    const size = length(node);
                    if (remaining <= size) {
                        const position = [...node.parentNode.childNodes].indexOf(node);
                        return [node.parentNode, position + (remaining > size / 2 ? 1 : 0)];
                    }
                    remaining -= size;
                } else if (node.nodeType === 3) remaining -= node.data.length;
                else for (const child of node.childNodes) { const result = find(child); if (result) return result; }
                return null;
            }
            return find(editor) || [editor, editor.childNodes.length];
        }
        function setSelection(start, end = start) {
            const size = source.value.length;
            selection = {start: Math.max(0, Math.min(start, size)), end: Math.max(0, Math.min(end, size))};
            if (document.activeElement !== editor) return;
            const range = document.createRange();
            range.setStart(...point(selection.start)); range.setEnd(...point(selection.end));
            const current = window.getSelection(); current.removeAllRanges(); current.addRange(range);
        }
        function refresh() {
            if (!active || composing) return;
            const emotes = getEmotes();
            if (catalogSource !== emotes) {
                catalogSource = emotes; catalog = new Map();
                for (const emote of emotes) {
                    if (typeof emote?.name === 'string' && /^https:\/\/(?:static-cdn\.jtvnw\.net|cdn\.7tv\.app)\//.test(emote.url || '') && !catalog.has(emote.name)) catalog.set(emote.name, emote);
                }
            }
            const useEmotes = enabled(), value = source.value;
            if (renderedText === value && renderedEnabled === useEmotes && renderedCatalog === catalog && text(editor) === value) return;
            const caret = readSelection();
            const fragment = document.createDocumentFragment();
            const images = new Map();
            for (const image of editor.querySelectorAll('img[data-emote-name]')) {
                const name = image.dataset.emoteName;
                if (!images.has(name)) images.set(name, []);
                images.get(name).push(image);
            }
            for (const token of value.split(/(\s+)/)) {
                if (!token) continue;
                const emote = useEmotes && catalog.get(token);
                if (emote) {
                    let image = images.get(token)?.shift();
                    if (!image || image.src !== emote.url) {
                        image = document.createElement('img');
                        image.className = 'chat-input-emote'; image.src = emote.url;
                        image.alt = token; image.title = token; image.dataset.emoteName = token;
                        image.contentEditable = 'false'; image.draggable = false;
                    }
                    fragment.append(image);
                } else fragment.append(document.createTextNode(token));
            }
            if (value.endsWith('\n')) { const tail = document.createElement('br'); tail.dataset.tail = 'true'; fragment.append(tail); }
            editor.replaceChildren(fragment);
            renderedText = value; renderedEnabled = useEmotes; renderedCatalog = catalog;
            setSelection(caret.start, caret.end);
        }
        function remember() {
            const caret = readSelection();
            undo.push({value: source.value, ...caret});
            if (undo.length > 100) undo.shift();
            redo.length = 0;
        }
        function notify() { editor.dispatchEvent(new Event('input', {bubbles: true})); }
        function replace(value, start, end, mode = 'end') {
            if (!active) return;
            // Expand replacements touching an emote so its text code is atomic too.
            let at = 0;
            for (const node of editor.childNodes) {
                const size = length(node);
                if (node.dataset?.emoteName) {
                    if (start > at && start < at + size) start = at;
                    if (end > at && end < at + size) end = at + size;
                }
                at += size;
            }
            const next = source.value.slice(0, start) + value + source.value.slice(end);
            if (next.length > source.maxLength) { onLimit(); return; }
            remember(); source.value = next; refresh();
            setSelection(mode === 'select' ? start : start + value.length, start + value.length);
        }
        function history(from, to) {
            if (!from.length) return;
            to.push({value: source.value, ...readSelection()});
            const entry = from.pop(); source.value = entry.value; refresh(); setSelection(entry.start, entry.end); notify();
        }
        function listen(target, type, handler) {
            target.addEventListener(type, handler); listeners.push(() => target.removeEventListener(type, handler));
        }
        listen(editor, 'beforeinput', event => {
            if (composing || event.isComposing) return;
            if (event.inputType.startsWith('format')) { event.preventDefault(); return; }
            const caret = readSelection();
            if (event.inputType === 'historyUndo' || event.inputType === 'historyRedo') {
                event.preventDefault(); event.inputType === 'historyUndo' ? history(undo, redo) : history(redo, undo); return;
            }
            if (event.inputType === 'insertParagraph' || event.inputType === 'insertLineBreak') {
                event.preventDefault(); replace('\n', caret.start, caret.end); notify(); return;
            }
            if (caret.start === caret.end && ['deleteContentBackward', 'deleteContentForward'].includes(event.inputType)) {
                let at = 0;
                for (const node of editor.childNodes) {
                    const size = length(node);
                    if (node.dataset?.emoteName && (event.inputType === 'deleteContentBackward' ? at + size === caret.start : at === caret.start)) {
                        event.preventDefault(); replace('', at, at + size); notify(); return;
                    }
                    at += size;
                }
            }
            remember();
        });
        listen(editor, 'input', () => {
            if (!active || composing) return;
            const caret = readSelection();
            const value = editor.childNodes.length === 1 && editor.firstChild.nodeName === 'BR' ? '' : text(editor);
            if (value.length > source.maxLength) { onLimit(); renderedText = null; refresh(); return; }
            source.value = value;
            refresh(); setSelection(caret.start, caret.end);
        });
        listen(editor, 'compositionstart', () => { remember(); composing = true; });
        listen(editor, 'compositionend', () => { composing = false; notify(); });
        listen(editor, 'keydown', event => {
            if (!event.isComposing && (event.ctrlKey || event.metaKey) && !event.altKey && ['z', 'y'].includes(event.key.toLowerCase())) {
                event.preventDefault();
                event.key.toLowerCase() === 'y' || event.shiftKey ? history(redo, undo) : history(undo, redo);
            }
        });
        for (const kind of ['copy', 'cut']) listen(editor, kind, event => {
            const caret = readSelection();
            if (caret.start === caret.end || !event.clipboardData) return;
            event.preventDefault(); event.clipboardData.setData('text/plain', source.value.slice(caret.start, caret.end));
            if (kind === 'cut') { replace('', caret.start, caret.end); notify(); }
        });
        listen(editor, 'paste', event => {
            if (!event.clipboardData) return;
            event.preventDefault(); const caret = readSelection();
            replace(event.clipboardData.getData('text/plain').replace(/\r\n?/g, '\n'), caret.start, caret.end); notify();
        });
        listen(editor, 'drop', event => {
            event.preventDefault(); const caret = readSelection();
            replace(event.dataTransfer?.getData('text/plain') || '', caret.start, caret.end); notify();
        });
        listen(document, 'selectionchange', readSelection);
        refresh();
        return {
            element: editor, source,
            get value() { return composing ? text(editor) : source.value; },
            set value(value) { source.value = value; undo.length = redo.length = 0; refresh(); },
            get maxLength() { return source.maxLength; },
            get placeholder() { return source.placeholder; },
            set placeholder(value) { source.placeholder = value; editor.setAttribute('aria-placeholder', value); },
            get selectionStart() { return readSelection().start; },
            get selectionEnd() { return readSelection().end; },
            get scrollTop() { return editor.scrollTop; },
            get style() { return editor.style; },
            setSelectionRange: setSelection,
            setRangeText: replace,
            focus() { editor.focus(); setSelection(selection.start, selection.end); },
            addEventListener: (...args) => editor.addEventListener(...args),
            removeEventListener: (...args) => editor.removeEventListener(...args),
            setAttribute: (...args) => editor.setAttribute(...args),
            dispatchEvent: event => editor.dispatchEvent(event),
            refreshEmotes: refresh,
            destroyEmoteInput() {
                if (!active) return;
                active = false; listeners.forEach(remove => remove());
                source.hidden = original.hidden; source.required = original.required; delete source.dataset.emoteSource; editor.remove();
            }
        };
    };
})();
