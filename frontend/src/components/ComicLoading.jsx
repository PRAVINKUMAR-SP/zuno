import { memo } from 'react';
import { Palette } from 'lucide-react';

const ComicLoading = memo(function ComicLoading({ message = 'Illustrating concept with XKCD comic...' }) {
  return (
    <div className="zuno-msg-enter my-3 mx-auto flex max-w-[520px] items-center justify-between rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-3.5 py-2.5 text-xs text-amber-200/90 shadow-sm">
      <div className="flex items-center gap-2.5">
        <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-500/15 text-amber-300">
          <Palette className="h-3.5 w-3.5 animate-pulse" />
        </span>
        <span className="font-medium tracking-wide">{message}</span>
      </div>

      <div className="flex items-center gap-1">
        <span className="zuno-audio-bar inline-block w-1 rounded-full bg-amber-400" style={{ animationDelay: '0ms' }} />
        <span className="zuno-audio-bar inline-block w-1 rounded-full bg-amber-300" style={{ animationDelay: '150ms' }} />
        <span className="zuno-audio-bar inline-block w-1 rounded-full bg-amber-400" style={{ animationDelay: '300ms' }} />
        <span className="zuno-audio-bar inline-block w-1 rounded-full bg-amber-300" style={{ animationDelay: '450ms' }} />
      </div>
    </div>
  );
});

export default ComicLoading;

