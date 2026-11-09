import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'danger'

type Props = {
  variant?: ButtonVariant
  /** Drawn beside the text. The text in `children` stays visible. */
  icon?: ReactNode
  loading?: boolean
  children: ReactNode
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children'>

/** Text label is required. Icon is optional and does not replace the label. */
export const Button = forwardRef<HTMLButtonElement, Props>(function Button({
  variant = 'primary',
  icon,
  loading = false,
  disabled,
  className,
  type = 'button',
  children,
  ...rest
}, ref) {
  const off = disabled || loading
  const classes = [
    'ca-btn',
    variant === 'secondary' ? 'ca-panel__secondary' : 'ca-panel__primary',
    variant === 'danger' ? 'ca-panel__danger' : '',
    `ca-btn--${variant}`,
    className,
  ].filter(Boolean).join(' ')
  return (
    <button
      {...rest}
      ref={ref}
      type={type}
      className={classes}
      disabled={off}
      aria-busy={loading || undefined}
      data-loading={loading || undefined}
    >
      {loading ? <span className="ca-btn__spin" aria-hidden="true" /> : icon ? <span className="ca-icon ca-btn__icon" aria-hidden="true">{icon}</span> : null}
      <span className="ca-btn__label">{children}</span>
    </button>
  )
})

/** Icon plus a visible label. There is no icon-only mode. */
export function IconButton({ icon, label, ...rest }: { icon: ReactNode; label: string } & Omit<Props, 'icon' | 'children'>) {
  return <Button icon={icon} {...rest}>{label}</Button>
}
