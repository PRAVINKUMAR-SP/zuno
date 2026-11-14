import { useState } from 'react';
import { AlertCircle, Check, Lock, Mail, Shield, User, X } from 'lucide-react';
import { loginUser, registerUser, setAuthSession } from '../api/zunoApi';

export default function AuthModal({ isOpen, onClose, onAuthSuccess, initialMode = 'login', quotaExceeded = false }) {
  const [mode, setMode] = useState(initialMode); // 'login' or 'register'
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setLoading(true);

    try {
      if (mode === 'register') {
        if (!name.trim()) {
          throw new Error('Please enter your full name');
        }
        const res = await registerUser(name, email, password);
        setAuthSession(res.token, res.user);
        setSuccessMsg(res.user.role === 'ROLE_ADMIN' ? 'Admin account created!' : 'Account registered successfully!');
        setTimeout(() => {
          onAuthSuccess?.(res.user);
          onClose();
        }, 600);
      } else {
        const res = await loginUser(email, password);
        setAuthSession(res.token, res.user);
        setSuccessMsg('Logged in successfully!');
        setTimeout(() => {
          onAuthSuccess?.(res.user);
          onClose();
        }, 500);
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md overflow-hidden rounded-2xl border border-white/[0.12] bg-[#12131a] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1 text-zinc-400 transition hover:bg-white/[0.08] hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>

        {quotaExceeded && (
          <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
            <div>
              <span className="font-semibold">Guest Limit Reached (5 Questions):</span>
              <p className="mt-0.5 text-zinc-300">
                Create a free account or log in to continue with unlimited private conversations, memory, and full AI access.
              </p>
            </div>
          </div>
        )}

        {/* Tab switch */}
        <div className="mb-6 flex rounded-xl border border-white/[0.08] bg-white/[0.03] p-1 text-xs font-medium">
          <button
            type="button"
            onClick={() => {
              setMode('login');
              setError('');
            }}
            className={`flex-1 rounded-lg py-2 transition ${
              mode === 'login' ? 'bg-white/[0.12] text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode('register');
              setError('');
            }}
            className={`flex-1 rounded-lg py-2 transition ${
              mode === 'register' ? 'bg-white/[0.12] text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Create Account
          </button>
        </div>

        <div className="mb-5 text-center">
          <h3 className="text-lg font-semibold text-white">
            {mode === 'login' ? 'Welcome Back to ZERO' : 'Create Your ZERO Profile'}
          </h3>
          <p className="mt-1 text-xs text-zinc-400">
            {mode === 'login'
              ? 'Access your private conversations and token history'
              : 'Every message is private and saved directly to your profile'}
          </p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-300">
            <div>{error}</div>
            {error.toLowerCase().includes('already exists') && (
              <button
                type="button"
                onClick={() => {
                  setMode('login');
                  setError('');
                }}
                className="mt-1.5 block font-semibold text-amber-400 underline hover:text-amber-300"
              >
                Click here to Sign In with this email &rarr;
              </button>
            )}
          </div>
        )}

        {successMsg && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3.5 py-2 text-xs text-emerald-300">
            <Check className="h-4 w-4" />
            <span>{successMsg}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {mode === 'register' && (
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-300">Full Name</label>
              <div className="relative">
                <User className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Praveen"
                  className="w-full rounded-xl border border-white/[0.1] bg-black/40 py-2 pl-9 pr-3 text-sm text-zinc-100 placeholder-zinc-600 focus:border-amber-400/60 focus:outline-none focus:ring-1 focus:ring-amber-400/40"
                />
              </div>
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-300">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full rounded-xl border border-white/[0.1] bg-black/40 py-2 pl-9 pr-3 text-sm text-zinc-100 placeholder-zinc-600 focus:border-amber-400/60 focus:outline-none focus:ring-1 focus:ring-amber-400/40"
              />
            </div>
            {mode === 'register' && email.toLowerCase().includes('pravin007ptk') && (
              <span className="mt-1 flex items-center gap-1 text-[11px] text-amber-300 font-medium">
                <Shield className="h-3 w-3" /> Designated Admin email detected
              </span>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-300">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-xl border border-white/[0.1] bg-black/40 py-2 pl-9 pr-3 text-sm text-zinc-100 placeholder-zinc-600 focus:border-amber-400/60 focus:outline-none focus:ring-1 focus:ring-amber-400/40"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="mt-5 w-full rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 py-2.5 text-xs font-semibold uppercase tracking-wider text-black transition hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Processing...' : mode === 'login' ? 'Sign In' : 'Create Profile'}
          </button>
        </form>
      </div>
    </div>
  );
}

