import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { ToastContainer } from '../components/ToastContainer'

export type ToastType = 'success' | 'error' | 'info'
export type Toast = { id: number; message: string; type: ToastType }

type ToastFn = (message: string, type?: ToastType) => void
const ToastContext = createContext<ToastFn>(() => {})

/** Call `toast('Saved', 'success')` from any component under <ToastProvider>. */
export function useToast(): ToastFn {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const idRef = useRef(0)
  const dismiss = useCallback((id: number) => setToasts(t => t.filter(x => x.id !== id)), [])
  const push = useCallback<ToastFn>((message, type = 'info') => {
    const id = ++idRef.current
    setToasts(t => [...t, { id, message, type }])
    setTimeout(() => dismiss(id), 3500)
  }, [dismiss])

  return (
    <ToastContext.Provider value={push}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}