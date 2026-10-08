import { useState, useCallback } from 'react'

export const useAutomationEvents = () => {
  const [events, setEvents] = useState<unknown[]>([])
  const [loading, setLoading] = useState(false)

  const addEvent = useCallback((event: unknown) => {
    setEvents((prev) => [event, ...prev].slice(0, 10))
  }, [])

  return { 
    events, 
    loading, 
    addEvent, 
    refetch: async () => {} 
  }
}