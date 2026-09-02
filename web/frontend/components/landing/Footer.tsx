import { Logo } from "./Logo";
import { GITHUB_URL, DEMO_URL } from "./styles";

export function Footer() {
  return (
    <footer className="k-footer">
      <div className="k-brand">
        <Logo size={20} />
        <span className="k-wordmark">KESTREL</span>
      </div>
      <p className="k-footer__line">
        Kestrel — an autonomous options agent. Built for the Alpaca AI Trading
        Agents Hackathon.
      </p>
      <div className="k-footer__links">
        <a href={GITHUB_URL} target="_blank" rel="noreferrer noopener">GitHub</a>
        <a href="/dashboard">Dashboard</a>
        <a href={DEMO_URL} target="_blank" rel="noreferrer noopener">Demo video</a>
      </div>
    </footer>
  );
}
