"use client";
import { useEffect, useState } from "react";
import { Logo } from "./Logo";
import { Cta } from "./Cta";
import { CONTACT_URL } from "./styles";

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 24);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);

  return (
    <header className={`k-nav${scrolled ? " k-nav--scrolled" : ""}`}>
      <a className="k-brand" href="#top" aria-label="Kestrel — top">
        <Logo size={20} />
        <span className="k-wordmark">KESTREL</span>
      </a>
      <nav className="k-navlinks" aria-label="Primary">
        <a className="k-navlink" href="#how-it-works">How it works</a>
        <a className="k-navlink" href="#proof">Track record</a>
        <a className="k-navlink" href="#membership">Membership</a>
        <a className="k-navlink" href={CONTACT_URL}>Contact</a>
        <a className="k-navlink" href="/login">Sign in</a>
        <Cta href="/login" variant="primary" size="sm" magnetic={false}>Get access</Cta>
      </nav>
    </header>
  );
}
