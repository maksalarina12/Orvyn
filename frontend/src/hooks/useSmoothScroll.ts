import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const SPEED = 0.62;
const EASING = 0.085;

function hasInnerScroll(target: EventTarget | null, deltaY: number): boolean {
  let el = target instanceof HTMLElement ? target : null;
  while (el && el !== document.body) {
    const style = window.getComputedStyle(el);
    const scrollable = /(auto|scroll)/.test(style.overflowY) && el.scrollHeight > el.clientHeight + 1;
    if (scrollable) {
      const atTop = el.scrollTop <= 0 && deltaY < 0;
      const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1 && deltaY > 0;
      if (!atTop && !atBottom) return true;
    }
    el = el.parentElement;
  }
  return false;
}

export function useSmoothScroll() {
  const { pathname } = useLocation();

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    if (window.matchMedia("(pointer: coarse)").matches) return;

    let target = window.scrollY;
    let current = target;
    let frame = 0;
    let animating = false;

    const maxScroll = () => Math.max(0, document.documentElement.scrollHeight - window.innerHeight);

    const tick = () => {
      current += (target - current) * EASING;
      if (Math.abs(target - current) < 0.4) {
        current = target;
        window.scrollTo(0, current);
        animating = false;
        return;
      }
      window.scrollTo(0, current);
      frame = window.requestAnimationFrame(tick);
    };

    const onWheel = (event: WheelEvent) => {
      if (event.ctrlKey || event.defaultPrevented) return;
      if (Math.abs(event.deltaY) < Math.abs(event.deltaX)) return;
      if (hasInnerScroll(event.target, event.deltaY)) return;
      if (document.querySelector(".palette-backdrop")) {
        event.preventDefault();
        return;
      }
      event.preventDefault();
      if (!animating) {
        current = window.scrollY;
        target = current;
      }
      target = Math.min(maxScroll(), Math.max(0, target + event.deltaY * SPEED));
      if (!animating) {
        animating = true;
        frame = window.requestAnimationFrame(tick);
      }
    };

    window.addEventListener("wheel", onWheel, { passive: false });

    const sync = window.setInterval(() => {
      if (!animating && Math.abs(window.scrollY - current) > 2) {
        current = window.scrollY;
        target = current;
      }
    }, 250);

    return () => {
      window.removeEventListener("wheel", onWheel);
      window.cancelAnimationFrame(frame);
      window.clearInterval(sync);
    };
  }, []);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
}
