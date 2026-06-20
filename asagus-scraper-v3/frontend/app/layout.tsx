import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";

export const metadata: Metadata = {
  title: "ASAGUS Scraper 3.0",
  description: "Intelligent scraping, enrichment and retrieval console"
};

const hydrationAttributeCleanup = `
(() => {
  const extensionAttrs = [
    "bis_skin_checked",
    "data-new-gr-c-s-check-loaded",
    "data-gr-ext-installed"
  ];

  const stripAttrs = (root) => {
    if (!root || root.nodeType !== Node.ELEMENT_NODE) return;

    for (const attr of extensionAttrs) {
      if (root.hasAttribute(attr)) root.removeAttribute(attr);
      root.querySelectorAll("[" + attr + "]").forEach((el) => el.removeAttribute(attr));
    }
  };

  stripAttrs(document.documentElement);

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === "attributes" && mutation.attributeName) {
        mutation.target.removeAttribute(mutation.attributeName);
        continue;
      }

      mutation.addedNodes.forEach(stripAttrs);
    }
  });

  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: extensionAttrs,
    childList: true,
    subtree: true
  });

  window.addEventListener("load", () => observer.disconnect(), { once: true });
})();
`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <Script
          id="hydration-extension-attribute-cleanup"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{ __html: hydrationAttributeCleanup }}
        />
        {children}
      </body>
    </html>
  );
}
