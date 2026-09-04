import Image from "next/image";

// Hero media isolated behind a single `src` prop. Swapping the still for a
// looping clip later is a one-line change: branch on the file extension and
// render a <video> with the same object-cover fill.
export function HeroMedia({ src, alt = "" }: { src: string; alt?: string }) {
  const isVideo = /\.(mp4|webm|mov)$/i.test(src);
  return (
    <div className="k-hero__media">
      {isVideo ? (
        <video src={src} autoPlay muted loop playsInline aria-hidden="true" />
      ) : (
        <Image
          src={src}
          alt={alt}
          fill
          priority
          sizes="100vw"
          style={{ objectFit: "cover" }}
        />
      )}
    </div>
  );
}
