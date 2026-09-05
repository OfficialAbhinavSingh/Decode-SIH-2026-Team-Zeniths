import { useEffect, useId, useRef, useState } from 'react'
import { DEBOUNCE_MS, MIN_QUERY, searchPlaces } from '../lib/geocode.js'

// Search a place by name and hand the caller back a point.
//
// This is one of three ways to set a location on the report form, not a replacement for
// the other two. GPS is still better when the resident is standing at the leak, and typed
// coordinates are still the path that works with no network at all. Search covers the case
// neither did: reporting a leak somewhere you are not, which is most reports made from a
// desk -- and it is the only one of the three that survives a denied permission prompt on
// a laptop with no GPS.
export default function LocationSearch({ onPick, disabled }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [active, setActive] = useState(-1)
  const boxRef = useRef(null)
  const listId = useId()

  // One debounce and one in-flight request. Aborting the previous fetch is what stops a
  // slow early query from landing after a fast later one and repopulating the list with
  // results for a prefix the user has already typed past.
  useEffect(() => {
    const q = query.trim()
    if (q.length < MIN_QUERY) {
      setResults([])
      setBusy(false)
      setError('')
      return undefined
    }
    const controller = new AbortController()
    setBusy(true)
    const timer = setTimeout(() => {
      searchPlaces(q, { signal: controller.signal })
        .then((found) => {
          setResults(found)
          setActive(-1)
          setOpen(true)
          setError(found.length === 0 ? `No place matched “${q}”.` : '')
        })
        .catch((err) => {
          if (err.name === 'AbortError') return
          setResults([])
          // Offline is the expected failure at a venue, and the form has two other ways
          // to set a point. Name them instead of leaving a dead end.
          setError('Place search is unreachable — use current location or type coordinates.')
        })
        .finally(() => {
          if (!controller.signal.aborted) setBusy(false)
        })
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  // Clicking a result must register before the dropdown closes, so this listens for a
  // press that lands outside the whole component rather than for the input losing focus.
  useEffect(() => {
    if (!open) return undefined
    const onDown = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const choose = (place) => {
    onPick(place)
    setQuery('')
    setResults([])
    setOpen(false)
    setActive(-1)
    setError('')
  }

  const onKeyDown = (e) => {
    // Enter inside a form submits it. While the dropdown is open Enter means "take the
    // highlighted result", so it must never reach the form -- otherwise picking a place
    // with the keyboard files the report instead.
    if (e.key === 'Enter') {
      if (open && active >= 0 && results[active]) {
        e.preventDefault()
        choose(results[active])
      } else if (open || query.trim()) {
        e.preventDefault()
      }
      return
    }
    if (e.key === 'Escape') {
      setOpen(false)
      setActive(-1)
      return
    }
    if (!results.length) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((i) => (i + 1) % results.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setOpen(true)
      setActive((i) => (i <= 0 ? results.length - 1 : i - 1))
    }
  }

  return (
    <div className="place-search" ref={boxRef}>
      <div className="place-search-field">
        <span className="place-search-icon" aria-hidden="true">⌕</span>
        <input
          type="text"
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          autoComplete="off"
          disabled={disabled}
          placeholder="Search a road, landmark or area…"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => results.length > 0 && setOpen(true)}
          onKeyDown={onKeyDown}
        />
        {busy && <span className="spinner place-search-spin" aria-hidden="true" />}
      </div>

      {open && results.length > 0 && (
        <ul className="place-results" id={listId} role="listbox">
          {results.map((place, i) => (
            <li key={place.id} role="option" aria-selected={i === active}>
              <button
                type="button"
                className={`place-result${i === active ? ' active' : ''}`}
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(place)}
              >
                <span className="place-result-title">{place.title}</span>
                {place.detail && <span className="place-result-detail">{place.detail}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="field-hint warn">{error}</p>}
    </div>
  )
}
