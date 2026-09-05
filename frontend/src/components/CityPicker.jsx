// Which city the dashboard is showing. Owner: R4 (Frontend).
//
// A native <select>, on purpose. There are a couple of hundred cities once the synthetic
// registry is loaded, and the browser's own control already gives us type-ahead, keyboard
// navigation, and a full-screen wheel on mobile -- all of which a hand-rolled combobox has
// to reimplement and usually gets wrong. It also cannot break the layout, which matters
// more than it looks for something sitting in the header of the one screen being demoed.
//
// It renders NOTHING when there is one city or fewer. A database holding only the seeded
// Jaipur grid is the case the dashboard has always had, and it must keep looking exactly
// like it always has -- an empty dropdown labelled "Jaipur" is worse than no dropdown.
export default function CityPicker({ cities, value, onChange }) {
  if (!cities || cities.length < 2) return null
  // Wait for the caller to know which city is on screen. /api/cities and the zone data are
  // two separate requests; if the list wins the race, rendering with no value would show
  // the alphabetically-first city for a frame -- the control would claim to be on Agartala
  // while the map loads Jaipur.
  if (!value) return null
  // A value the list does not contain would make the browser display the first option
  // while reporting the real one, so the control would silently lie about its own state.
  if (!cities.some((c) => c.city === value)) return null

  return (
    <label className="city-picker">
      <span className="sr-only">City</span>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11Z"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <circle cx="12" cy="10" r="2.4" stroke="currentColor" strokeWidth="1.8" />
      </svg>
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        aria-label={`City — ${cities.length} loaded`}
      >
        {cities.map((c) => (
          <option key={c.city} value={c.city}>
            {c.city} ({c.zone_count})
          </option>
        ))}
      </select>
    </label>
  )
}
