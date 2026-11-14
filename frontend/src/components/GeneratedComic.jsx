import { memo, useState } from 'react';
import { Check, Copy, Download, Maximize2, X } from 'lucide-react';

const GeneratedComic = memo(function GeneratedComic({ visual }) {
  const [copied, setCopied] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [imgError, setImgError] = useState(false);

  if (!visual || !visual.imageUrl || imgError) {
    return null;
  }

  const { imageUrl, filename } = visual;

  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(imageUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Ignore
    }
  };

  const handleDownload = (e) => {
    e.stopPropagation();
    const a = document.createElement('a');
    a.href = imageUrl;
    a.download = filename || 'comic.png';
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <>
      <div className="zuno-msg-enter my-4 flex w-full justify-center">
        <div
          onClick={() => setModalOpen(true)}
          className="group relative w-full max-w-[720px] cursor-pointer overflow-hidden rounded-2xl border border-white/[0.12] bg-white p-2.5 shadow-xl transition-all duration-200 hover:border-white/30 hover:shadow-2xl"
        >
          {/* Subtle floating actions on hover */}
          <div className="absolute right-4 top-4 z-10 flex items-center gap-1.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
            <button
              type="button"
              onClick={handleCopy}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-black/75 text-white shadow-md backdrop-blur-sm transition hover:bg-black"
              title="Copy link"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
            <button
              type="button"
              onClick={handleDownload}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-black/75 text-white shadow-md backdrop-blur-sm transition hover:bg-black"
              title="Download PNG"
            >
              <Download className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-black/75 text-white shadow-md backdrop-blur-sm transition hover:bg-black"
              title="Enlarge comic"
            >
              <Maximize2 className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Centered Comic Image */}
          <img
            src={imageUrl}
            alt="Comic illustration"
            onError={() => setImgError(true)}
            className="mx-auto block max-h-[420px] w-auto rounded object-contain transition-transform duration-200 group-hover:scale-[1.01]"
            loading="lazy"
          />

          {/* Click to enlarge overlay hint */}
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition-opacity duration-200 group-hover:bg-black/5 group-hover:opacity-100">
            <span className="rounded-full bg-black/75 px-3 py-1 text-xs text-white backdrop-blur-sm">
              Click to enlarge
            </span>
          </div>
        </div>
      </div>

      {/* Lightbox Modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-sm"
          onClick={() => setModalOpen(false)}
        >
          <div
            className="relative max-h-[92vh] max-w-5xl overflow-hidden rounded-2xl border border-white/20 bg-[#121319] p-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center justify-end">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="rounded-lg p-1.5 text-zinc-400 transition hover:bg-white/[0.08] hover:text-white"
                title="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="overflow-auto rounded-xl bg-white p-3">
              <img
                src={imageUrl}
                alt="Comic Full"
                className="mx-auto max-h-[80vh] w-auto object-contain"
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
});

export default GeneratedComic;
