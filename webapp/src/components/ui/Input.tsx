import { forwardRef, useState } from 'react'
import { Eye, EyeOff, HelpCircle } from 'lucide-react'

interface Props extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  showHelp?: boolean
}

export const Input = forwardRef<HTMLInputElement, Props>(({ label, className = '', type, error, showHelp, ...rest }, ref) => {
  const [showPass, setShowPass] = useState(false)
  const isPassword = type === 'password'
  const currentType = isPassword ? (showPass ? 'text' : 'password') : type

  return (
    <div className="flex flex-col gap-1.5 w-full">
      {(label || showHelp) && (
        <div className="flex items-center justify-between px-0.5">
          {label && (
            <label className="text-[13px] font-medium text-t-secondary">
              {label}
            </label>
          )}
          {showHelp && <HelpCircle size={13} className="text-t-muted cursor-help" />}
        </div>
      )}

      <div className="relative">
        <input
          ref={ref}
          type={currentType}
          className={[
            'w-full rounded-md px-3 py-2 text-[14px]',
            'bg-surface-input text-t-primary',
            'placeholder:text-t-placeholder',
            'outline-none transition-shadow duration-150',
            'shadow-[var(--shadow-border)]',
            'focus:shadow-[0_0_0_2px_var(--b-focus)]',
            'disabled:opacity-40 disabled:cursor-not-allowed',
            error
              ? 'shadow-[0_0_0_1px_var(--semantic-error)] focus:shadow-[0_0_0_2px_var(--semantic-error)]'
              : '',
            className,
          ].join(' ')}
          {...rest}
        />

        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPass(!showPass)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-t-muted hover:text-t-primary transition-colors"
          >
            {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        )}
      </div>

      {error && (
        <p className="text-[12px] text-[var(--semantic-error)] font-medium px-0.5">{error}</p>
      )}
    </div>
  )
})

Input.displayName = 'Input'
