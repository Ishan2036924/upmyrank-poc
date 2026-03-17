declare module 'react-katex' {
  import { ComponentProps } from 'react'

  interface MathProps {
    math: string
    errorColor?: string
    renderError?: (error: Error) => React.ReactNode
    settings?: Record<string, unknown>
  }

  export function InlineMath(props: MathProps): JSX.Element
  export function BlockMath(props: MathProps): JSX.Element
}
