import { partImg } from "../assets";

export function PartGallery({ labels, className = "part-gallery" }: { labels: string[]; className?: string }) {
  return (
    <div className={className}>
      {labels.map((label, i) => (
        <div className="part-tile" key={`${label}-${i}`} style={{ animationDelay: `${i * 55}ms` }}>
          <img src={partImg(i)} alt={label} />
          <span>{label}</span>
        </div>
      ))}
    </div>
  );
}
