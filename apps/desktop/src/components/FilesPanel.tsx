import { useState } from 'react'
import { formatFileSize } from '../utils/formatters'

export function FilesPanel() {
  return (
    <div style={{ padding: '20px', color: '#94a3b8' }}>
      <h3 style={{ color: '#f8fafc', marginBottom: '12px' }}>📁 文件管理</h3>
      <p>文件管理功能需要桌面端环境支持，当前为 Web 模式。</p>
      <p style={{ marginTop: '8px', fontSize: '13px', color: '#64748b' }}>
        请通过后端 API 直接操作文件系统。
      </p>
    </div>
  )
}