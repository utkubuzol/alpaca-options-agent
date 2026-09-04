import { Logo } from "./Logo";
import { GITHUB_URL, CONTACT_URL, CONTACT_EMAIL, MEMBERSHIP_URL } from "./styles";

export function Footer() {
  return (
    <footer className="k-footer" id="membership">
      <div className="k-brand">
        <Logo size={20} />
        <span className="k-wordmark">KESTREL</span>
      </div>
      <p className="k-footer__line">
        Membership is invite-based while the strategy is in paper. Members get the
        live dashboard, per-trade Telegram alerts, and the full decision journal —
        every signal, every rejection, every fill. Request access below or write
        to <a href={CONTACT_URL}>{CONTACT_EMAIL}</a>.
      </p>
      <div className="k-footer__links">
        <a href={MEMBERSHIP_URL}>Get access</a>
        <a href={CONTACT_URL}>Contact us</a>
        <a href={GITHUB_URL} target="_blank" rel="noreferrer noopener">GitHub</a>
      </div>
      <p className="k-footer__line" style={{ opacity: 0.7 }}>
        Kestrel operates in a simulated (paper) account. Nothing here is
        investment advice or a solicitation, and past simulated results do not
        imply future returns.
      </p>
    </footer>
  );
}
