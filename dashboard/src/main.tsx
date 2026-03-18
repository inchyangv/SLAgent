import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App'
import { WalletProvider } from './providers/WalletProvider'
import './index.css'

const rootEl = document.getElementById('root')!

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <WalletProvider>
      <App />
    </WalletProvider>
  </React.StrictMode>,
)
