import { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Sparkles, X, Send, Bot, User, Loader2, MapPin } from 'lucide-react'
import { cn } from '@/lib/utils'
<<<<<<< HEAD
import { sendChatMessage } from '@/lib/api'
=======

// ── Markdown renderer ─────────────────────────────────────────
function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return <em key={i}>{part.slice(1, -1)}</em>
    }
    return <span key={i}>{part}</span>
  })
}

function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n')
  const nodes: React.ReactNode[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    if (line.trim() === '') {
      nodes.push(<div key={i} className="h-1" />)
    } else if (line.startsWith('### ')) {
      nodes.push(
        <p key={i} className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mt-2 mb-0.5">
          {renderInline(line.slice(4))}
        </p>
      )
    } else if (line.startsWith('## ')) {
      nodes.push(
        <p key={i} className="text-xs font-bold text-foreground mt-2 mb-0.5">
          {renderInline(line.slice(3))}
        </p>
      )
    } else if (/^[-•]\s/.test(line)) {
      nodes.push(
        <div key={i} className="flex gap-1.5 items-start">
          <span className="text-primary/70 mt-0.5 flex-shrink-0">•</span>
          <span className="leading-relaxed">{renderInline(line.replace(/^[-•]\s/, ''))}</span>
        </div>
      )
    } else if (/^\d+\.\s/.test(line)) {
      const match = line.match(/^(\d+)\.\s(.*)$/)
      if (match) {
        nodes.push(
          <div key={i} className="flex gap-1.5 items-start">
            <span className="text-primary/70 font-mono text-[10px] mt-0.5 flex-shrink-0 w-3">{match[1]}.</span>
            <span className="leading-relaxed">{renderInline(match[2])}</span>
          </div>
        )
      }
    } else {
      nodes.push(
        <p key={i} className="leading-relaxed">{renderInline(line)}</p>
      )
    }

    i++
  }

  return <div className="space-y-0.5 text-sm">{nodes}</div>
}
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e

// ── Types ─────────────────────────────────────────────────────
interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
}

interface ChatWidgetProps {
  locationContext: { lat: number; lng: number } | null
}

// ── ChatWidget ────────────────────────────────────────────────
export function ChatWidget({ locationContext }: ChatWidgetProps) {
  const [isOpen,      setIsOpen]      = useState(false)
  const [messages,    setMessages]    = useState<Message[]>([])
  const [inputValue,  setInputValue]  = useState('')
  const [isLoading,   setIsLoading]   = useState(false)
  const [nextId,      setNextId]      = useState(1)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef       = useRef<HTMLInputElement>(null)

  const scrollToBottom = () =>
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })

  useEffect(() => { scrollToBottom() }, [messages, isLoading])

  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 150)
  }, [isOpen])

  // ── Core send logic — EXACT API contract preserved ─────────
  const sendMessage = async () => {
    const text = inputValue.trim()
    if (!text || isLoading) return

    const userMsg: Message = { id: nextId, role: 'user', content: text }
    setNextId((n) => n + 2)
    setMessages((prev) => [...prev, userMsg])
    setInputValue('')
    setIsLoading(true)

    try {
      // History sent WITHOUT the message we just added (match backend expectation)
      const history = messages.map(({ role, content }) => ({ role, content }))

<<<<<<< HEAD
      const data = await sendChatMessage({
        message: text,
        history,
        location_context: locationContext,
      })

=======
      const payload = {
        message: text,
        history,
        location_context: locationContext, // { lat, lng } | null
      }

      const res = await fetch('http://127.0.0.1:8001/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: { reply: string } = await res.json()

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
      setMessages((prev) => [
        ...prev,
        { id: nextId + 1, role: 'assistant', content: data.reply },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId + 1,
          role: 'assistant',
<<<<<<< HEAD
          content: '⚠️ Could not connect to the backend AI. Make sure the FastAPI server is running on port 8000.',
=======
          content: '⚠️ Could not connect to the backend AI. Make sure the FastAPI server is running on port 8001.',
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendMessage()
    }
  }

  return (
    <>
      {/* ── Chat Panel ──────────────────────────────────────── */}
      <div
        className={cn(
          'fixed bottom-24 right-6 w-[380px] h-[520px] rounded-2xl overflow-hidden transition-all duration-300 ease-out z-[9999]',
          'bg-card/95 backdrop-blur-xl border border-border shadow-2xl shadow-primary/10',
          isOpen
            ? 'opacity-100 scale-100 translate-y-0'
            : 'opacity-0 scale-95 translate-y-4 pointer-events-none',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 bg-secondary/50 backdrop-blur border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
              <Bot className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-foreground">DataSiteAI Assistant</h3>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <p className="text-xs text-muted-foreground">
                  {locationContext
                    ? `Site: ${locationContext.lat.toFixed(3)}, ${locationContext.lng.toFixed(3)}`
                    : 'Always online'}
                </p>
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg hover:bg-secondary"
            onClick={() => setIsOpen(false)}
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Messages */}
        <div className="flex-1 h-[calc(100%-128px)] overflow-y-auto p-4 space-y-4">
          {/* Empty state */}
          {messages.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 border border-border flex items-center justify-center">
                <Bot className="w-6 h-6 text-primary/60" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground mb-1">DataSiteAI Assistant</p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Ask me about data center suitability, power grids, climate risk, or real estate.
                  {locationContext && (
                    <span className="flex items-center gap-1 justify-center mt-1.5 text-emerald-600 dark:text-emerald-400">
                      <MapPin className="w-3 h-3" />
                      Site selected — I have location context.
                    </span>
                  )}
                </p>
              </div>
            </div>
          )}

          {/* Message list */}
          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                'flex gap-3',
                message.role === 'user' ? 'justify-end' : 'justify-start',
              )}
            >
              {message.role === 'assistant' && (
                <div className="w-7 h-7 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5 text-primary" />
                </div>
              )}
              <div
                className={cn(
<<<<<<< HEAD
                  'max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground rounded-br-sm'
                    : 'bg-secondary/80 backdrop-blur text-foreground border border-border rounded-bl-sm',
                )}
              >
                {message.content}
=======
                  'max-w-[80%] rounded-2xl px-4 py-2.5',
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground rounded-br-sm text-sm leading-relaxed'
                    : 'bg-secondary/80 backdrop-blur text-foreground border border-border rounded-bl-sm',
                )}
              >
                {message.role === 'assistant'
                  ? renderMarkdown(message.content)
                  : message.content}
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
              </div>
              {message.role === 'user' && (
                <div className="w-7 h-7 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <User className="w-3.5 h-3.5 text-primary" />
                </div>
              )}
            </div>
          ))}

          {/* Loading indicator */}
          {isLoading && (
            <div className="flex gap-3 justify-start">
              <div className="w-7 h-7 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot className="w-3.5 h-3.5 text-primary" />
              </div>
              <div className="bg-secondary/80 border border-border rounded-2xl rounded-bl-sm px-4 py-2.5 flex items-center gap-2">
                <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
                <span className="text-sm text-muted-foreground">Thinking…</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-card/95 backdrop-blur border-t border-border">
          <div className="flex items-center gap-2">
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={locationContext ? 'Ask about this site…' : 'Ask about site analysis…'}
              disabled={isLoading}
              className="flex-1 bg-secondary/50 border-border focus-visible:ring-primary/50 placeholder:text-muted-foreground"
            />
            <Button
              size="icon"
              onClick={() => void sendMessage()}
              disabled={isLoading || !inputValue.trim()}
              className="h-10 w-10 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/25 transition-all hover:shadow-primary/40 hover:scale-105 disabled:scale-100"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* ── Floating Action Button ───────────────────────────── */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'fixed bottom-6 right-6 w-14 h-14 rounded-full flex items-center justify-center z-[9999]',
          'bg-primary text-primary-foreground shadow-xl shadow-primary/30',
          'transition-all duration-300 ease-out hover:scale-110 hover:shadow-primary/50',
          'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
        )}
        aria-label="Open AI assistant"
      >
        <div className="absolute inset-0 rounded-full bg-primary animate-ping opacity-25" />
        {locationContext && (
          <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 border-2 border-background flex items-center justify-center">
            <MapPin className="w-2 h-2 text-white" />
          </div>
        )}
        <Sparkles
          className={cn(
            'w-6 h-6 relative z-10 transition-transform duration-300',
            isOpen ? 'rotate-45' : 'rotate-0',
          )}
        />
      </button>
    </>
  )
}
