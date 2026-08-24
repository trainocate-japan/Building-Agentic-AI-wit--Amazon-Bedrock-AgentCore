'use client'

import type { ReactNode } from 'react'
import { Amplify } from 'aws-amplify'
import { Authenticator } from '@aws-amplify/ui-react'
import '@aws-amplify/ui-react/styles.css'

// Amplify の初期設定
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: process.env.NEXT_PUBLIC_USER_POOL_ID || '',
      userPoolClientId: process.env.NEXT_PUBLIC_USER_POOL_CLIENT_ID || '',
    },
  },
})

// 認証プロバイダーコンポーネント
export function AuthProvider({ children }: { children: ReactNode }) {
  return <Authenticator>{children}</Authenticator>
}
