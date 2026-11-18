// The transition lives after the source content; only active user input can
// activate it. Scroll/restore/reflow merely update its visibility.
export class ReaderBookEnd {
  constructor({ stage, getBoundary, getNext, isLast, canInteract, onNext }) {
    Object.assign(this, { stage, getBoundary, getNext, isLast, canInteract, onNext });
    this.panel = stage.ownerDocument.createElement('section');
    this.panel.id = 'reader-book-end'; this.panel.className = 'reader-book-end';
    this.panel.setAttribute('aria-label', '书尾');
    this.title = stage.ownerDocument.createElement('p'); this.title.textContent = '本书完';
    this.button = stage.ownerDocument.createElement('button'); this.button.type = 'button';
    this.button.className = 'reader-button'; this.button.id = 'reader-book-end-next';
    this.hint = stage.ownerDocument.createElement('p');
    this.panel.append(this.title, this.button, this.hint);
    this.button.addEventListener('click', () => void this.next(true));
    stage.addEventListener('scroll', () => this.update(), { passive: true });
    this.bind(stage);
  }
  atEnd() {
    const boundary = this.getBoundary();
    return boundary != null && boundary <= this.stage.scrollTop + this.stage.clientHeight + 2;
  }
  update() {
    const boundary = this.getBoundary();
    // Keep an already visible/focused control stable during a layout change.
    if (boundary == null && !this.canInteract()) return;
    const visible = boundary != null && this.atEnd();
    if (visible && !this.panel.isConnected) this.stage.append(this.panel);
    this.panel.hidden = !visible;
    const next = this.getNext();
    this.button.hidden = !next;
    this.button.disabled = this.switching;
    this.button.textContent = next ? `下一本《${next.title || next.name || '未命名'}》` : '';
    this.hint.textContent = this.error || (next ? '继续上滑打开' : this.isLast() ? '已到书单末尾' : '');
    if (visible && this.touch && this.touch.tailY == null) this.touch.tailY = this.touch.y;
  }
  reset() {
    this.panel.remove(); this.touch = null; this.error = '';
    this.lastWheel = 0; this.wheelDistance = 0; this.wheelArmed = false;
  }
  async next(explicit = false) {
    if (this.switching || !this.getNext()) return;
    if (explicit ? !this.panel.isConnected || this.panel.hidden : !this.canInteract() || !this.atEnd()) return;
    if (this.touch || this.wheelArmed) {
      // A compositor scroll belongs to its original book even after its iframe
      // disappears. Keep the next book fixed until a fresh input starts.
      this.inputLocked = true;
      this.stage.style.overflow = 'hidden';
    }
    this.error = '';
    this.switching = true; this.touch = null; this.wheelArmed = false;
    this.button.disabled = true;
    try { await this.onNext(); }
    catch (error) { this.error = `下一本尚未打开：${error.message}`; }
    finally { this.switching = false; this.lastWheel = Date.now(); this.update(); }
  }
  bind(target) {
    if (!target || target.__readerBookEndBound) return;
    target.__readerBookEndBound = true;
    const unlock = () => {
      if (!this.inputLocked || this.switching) return;
      this.inputLocked = false;
      this.stage.style.overflow = '';
    };
    target.addEventListener('pointerdown', unlock, { capture: true, passive: true });
    target.addEventListener('keydown', unlock, true);
    const selection = () => target.getSelection?.()?.toString() || target.ownerDocument?.getSelection?.()?.toString();
    // Iframe coordinates move as the outer stage scrolls. Convert each input
    // back into the top-level viewport before measuring finger movement.
    const point = (touch) => ({ x: touch.clientX + (target.defaultView?.frameElement?.getBoundingClientRect().left || 0),
      y: touch.clientY + (target.defaultView?.frameElement?.getBoundingClientRect().top || 0) });
    target.addEventListener('touchstart', (event) => {
      unlock();
      this.touch = null;
      if (!this.canInteract() || this.switching || event.touches.length !== 1 || selection()
          || event.target.closest?.('button,a,input,textarea,select,img,[contenteditable="true"]')) return;
      const p = point(event.touches[0]);
      this.touch = { ...p, startX: p.x, startY: p.y, tailY: this.atEnd() ? p.y : null };
    }, { passive: true });
    target.addEventListener('touchmove', (event) => {
      if (!this.touch) return;
      if (event.touches.length !== 1 || selection() || !this.canInteract()) { this.touch = null; return; }
      const p = point(event.touches[0]), previous = this.touch;
      if (p.y > previous.y + 3 || Math.abs(p.x - previous.startX) > Math.max(32, Math.abs(p.y - previous.startY))) {
        this.touch = null; return;
      }
      previous.x = p.x; previous.y = p.y;
      if (!this.atEnd()) previous.tailY = null;
      else if (previous.tailY == null) previous.tailY = p.y;
      else if (previous.tailY - p.y >= 64) void this.next();
    }, { passive: true });
    for (const name of ['touchend', 'touchcancel']) target.addEventListener(name, () => { this.touch = null; }, { passive: true });
    target.addEventListener('wheel', (event) => {
      const now = Date.now(), newBurst = now - (this.lastWheel || 0) > 220;
      this.lastWheel = now;
      if (this.inputLocked && !newBurst) { event.preventDefault(); return; }
      if (newBurst) unlock();
      if (!this.canInteract() || this.switching || event.ctrlKey || selection()) return;
      if (newBurst) { this.wheelArmed = this.atEnd(); this.wheelDistance = 0; }
      if (event.deltaY <= 0 || !this.atEnd()) { this.wheelArmed = false; this.wheelDistance = 0; return; }
      if (this.wheelArmed) {
        this.wheelDistance += event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? this.stage.clientHeight : 1);
        if (this.wheelDistance >= 64) { event.preventDefault(); void this.next(); }
      }
      // A cancelable listener observes the pre-scroll position, before the
      // compositor can turn a wheel event that merely reaches the tail into intent.
    }, { passive: false });
  }
}
