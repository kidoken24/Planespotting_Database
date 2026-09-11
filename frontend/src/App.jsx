import { useState, useEffect } from 'react'
import './App.css' 

const getCountryFlag = (registration) => {
    if (!registration) return '✈️';
    const regUpper = registration.toUpperCase();
    const prefixMap = {
      'D-': '🇩🇪', 'G-': '🇬🇧', 'F-': '🇫🇷', 'N': '🇺🇸', 'C-': '🇨🇦', 
      'VH-': '🇦🇺', 'ZK-': '🇳🇿', 'JA': '🇯🇵', 'B-': '🇨🇳', 'A6-': '🇦🇪', 
      'A7-': '🇶🇦', '9V-': '🇸🇬', 'PH-': '🇳🇱', 'HB-': '🇨🇭', 'OE-': '🇦🇹', 
      'EC-': '🇪🇸', 'EI-': '🇮🇪', 'TC-': '🇹🇷', 'OH-': '🇫🇮', 'SE-': '🇸🇪', 
      'LN-': '🇳🇴', 'OY-': '🇩🇰', 'CS-': '🇵🇹', 'I-': '🇮🇹', 'SX-': '🇬🇷', 
      'SP-': '🇵🇱', 'OK-': '🇨🇿', 'OM-': '🇸🇰', 'HA-': '🇭🇺', 'VT-': '🇮🇳', 
      'HL': '🇰🇷', '9M-': '🇲🇾', 'PK-': '🇮🇩', 'HS-': '🇹🇭', 'SU-': '🇪🇬', 
      'ZS-': '🇿🇦', 'PR-': '🇧🇷', 'LV-': '🇦🇷', 'XA-': '🇲🇽'
    };
    const matchedPrefix = Object.keys(prefixMap)
      .sort((a, b) => b.length - a.length)
      .find(prefix => regUpper.startsWith(prefix));
    return matchedPrefix ? prefixMap[matchedPrefix] : '🏳️';
}

function App() {
  const [token, setToken] = useState(localStorage.getItem('spotting_token'))
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError] = useState(false)

  const [photos, setPhotos] = useState([])
  const [isUploading, setIsUploading] = useState(false)
  const [showForm, setShowForm] = useState(false)

  const [groupBy, setGroupBy] = useState('airline') 
  const [selectedRegPhotos, setSelectedRegPhotos] = useState(null) 
  const [selectedPhotoDetails, setSelectedPhotoDetails] = useState(null) 
  const [searchQuery, setSearchQuery] = useState('')

  const handleLogin = async (e) => {
    e.preventDefault()
    try {
      // NOTE: Remember to change this IP during your deployment loop!
      const response = await fetch('http://127.0.0.1:8000/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: loginPassword })
      })
      if (response.ok) {
        const data = await response.json()
        localStorage.setItem('spotting_token', data.token)
        setToken(data.token)
        setLoginError(false)
      } else {
        setLoginError(true)
      }
    } catch (error) {
      console.error("Login failed", error)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('spotting_token')
    setToken(null)
  }

  const fetchPhotos = () => {
    if (!token) return;
    fetch('http://127.0.0.1:8000/api/photos', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(response => {
          if (response.status === 401) handleLogout();
          return response.json()
      })
      .then(data => setPhotos(data))
      .catch(error => console.error("Error:", error))
  }

  useEffect(() => {
    fetchPhotos()
  }, [token]) 

  const handleUpload = async (event) => {
    event.preventDefault()
    setIsUploading(true)
    const formData = new FormData(event.target)

    try {
      const response = await fetch('http://127.0.0.1:8000/api/photos', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }, 
        body: formData, 
      })

      if (response.ok) {
        event.target.reset()
        fetchPhotos()
        setShowForm(false)
      }
    } finally {
      setIsUploading(false)
    }
  }

  const handleDelete = async (id) => {
    const confirmDelete = window.confirm("Are you sure you want to delete this photo?");
    if (!confirmDelete) return;

    const response = await fetch(`http://127.0.0.1:8000/api/photos/${id}`, {
      method: 'DELETE',
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (response.ok) {
      fetchPhotos();
      setSelectedPhotoDetails(null);
      setSelectedRegPhotos(null); 
    }
  }

  // UPDATED: Added location filtering and grouping logic
  const getGroupedPhotos = () => {
    const groups = {}
    
    const filteredPhotos = photos.filter(photo => {
      if (!searchQuery) return true 
      const query = searchQuery.toLowerCase()
      const reg = photo.registration ? photo.registration.toLowerCase() : ''
      const isoDate = photo.capture_date ? photo.capture_date.toLowerCase() : ''
      const localDate = photo.capture_date ? new Date(photo.capture_date).toLocaleDateString().toLowerCase() : ''
      const location = photo.airport ? photo.airport.toLowerCase() : '' // Added location to search
      
      return reg.includes(query) || isoDate.includes(query) || localDate.includes(query) || location.includes(query)
    })

    filteredPhotos.forEach(photo => {
      // Determine what to group by based on the current state
      let mainCategory = 'Unknown';
      if (groupBy === 'airline') mainCategory = photo.airline;
      else if (groupBy === 'aircraft_type') mainCategory = photo.aircraft_type;
      else if (groupBy === 'location') mainCategory = photo.airport;

      const categoryKey = mainCategory || 'Unknown'
      const regKey = photo.registration || 'Unknown'

      if (!groups[categoryKey]) groups[categoryKey] = {}
      if (!groups[categoryKey][regKey]) groups[categoryKey][regKey] = []
      
      groups[categoryKey][regKey].push(photo)
    })
    return groups
  }

  const groupedData = getGroupedPhotos()

  // --- LOGIN SCREEN ---
  if (!token) {
    return (
      <div className="login-container">
        <div className="login-card">
          <h2 className="app-title">✈️ Restricted Access</h2>
          <p className="text-muted">Please enter your master password.</p>
          <form onSubmit={handleLogin} className="login-form">
            <input 
              type="password" 
              value={loginPassword} 
              onChange={e => setLoginPassword(e.target.value)} 
              placeholder="Password" 
              className="form-input"
              required
            />
            {loginError && <span className="error-text">Incorrect password</span>}
            <button type="submit" className="btn btn-primary">Log In</button>
          </form>
        </div>
      </div>
    )
  }

  // --- VIEW 3: FULL PHOTO DETAILS ---
  if (selectedPhotoDetails) {
    return (
      <div className="app-container">
        <button onClick={() => setSelectedPhotoDetails(null)} className="btn btn-secondary">
          ⬅ Back to Gallery
        </button>
        <div className="detail-layout">
          <img 
            src={`http://127.0.0.1:8000/${selectedPhotoDetails.filepath}`} 
            alt={selectedPhotoDetails.registration} 
            className="detail-img"
          />
          <div className="detail-sidebar">
            <h2 className="app-title" style={{textAlign: 'left', marginBottom: '15px'}}>
              {getCountryFlag(selectedPhotoDetails.registration)} {selectedPhotoDetails.registration}
            </h2>
            <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '15px 0' }}/>
            <p className="detail-data"><strong>Airline:</strong> {selectedPhotoDetails.airline}</p>
            <p className="detail-data"><strong>Operator:</strong> {selectedPhotoDetails.operator}</p>
            <p className="detail-data"><strong>Aircraft Type:</strong> {selectedPhotoDetails.aircraft_type}</p>
            <p className="detail-data"><strong>Serial Number:</strong> {selectedPhotoDetails.serial_number}</p>
            <p className="detail-data"><strong>Airport (Location):</strong> {selectedPhotoDetails.airport}</p>
            <p className="detail-data"><strong>Country:</strong> {selectedPhotoDetails.country}</p>
            <p className="detail-data"><strong>Departure:</strong> {selectedPhotoDetails.departure_airport}</p>
            <p className="detail-data"><strong>Arrival:</strong> {selectedPhotoDetails.arrival_airport}</p>
            <p className="detail-data"><strong>Flight Number:</strong> {selectedPhotoDetails.flight_number}</p>
            <p className="detail-data"><strong>Capture Date (UTC):</strong> {new Date(selectedPhotoDetails.capture_date).toLocaleString()}</p>
            <p className="text-muted" style={{ marginTop: '20px' }}>File: {selectedPhotoDetails.filename}</p>

            <div className="detail-actions">
              <a 
                href={`http://127.0.0.1:8000/${selectedPhotoDetails.filepath}`} 
                download={selectedPhotoDetails.filename}
                target="_blank"
                rel="noreferrer"
                className="btn btn-primary"
              >
                ⬇️ Download Original
              </a>
              <button 
                onClick={() => handleDelete(selectedPhotoDetails.id)} 
                className="btn btn-danger"
              >
                🗑️ Delete Photo
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // --- VIEW 2: REGISTRATION GALLERY ---
  if (selectedRegPhotos) {
    const regName = selectedRegPhotos[0].registration
    return (
      <div className="app-container">
        <button onClick={() => setSelectedRegPhotos(null)} className="btn btn-secondary">
          ⬅ Back to Categories
        </button>
        <h2 className="app-title" style={{ textAlign: 'left', marginTop: '20px', marginBottom: '5px' }}>
          {getCountryFlag(regName)} All Captures for {regName}
        </h2>
        <p className="text-muted">{selectedRegPhotos.length} photo(s) found</p>

        <div className="photo-grid">
          {selectedRegPhotos.map(photo => (
            <div 
              key={photo.id} 
              onClick={() => setSelectedPhotoDetails(photo)} 
              className="photo-card"
            >
              <img 
                src={`http://127.0.0.1:8000/${photo.thumbnail_path}`} 
                alt="thumbnail" 
                className="photo-img"
              />
              <div className="photo-card-info">
                <p style={{ margin: 0, fontWeight: '500' }}>{photo.airport || 'Unknown Location'}</p>
                <p className="text-muted" style={{ margin: '5px 0 0 0' }}>
                  {new Date(photo.capture_date).toLocaleDateString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // --- VIEW 1: MAIN DASHBOARD ---
  return (
    <div className="app-container">
      
      <button onClick={handleLogout} className="btn btn-secondary btn-logout">
        Log Out
      </button>

      <h1 className="app-title">✈️ My Spotting Hangar</h1>
      
      <div className="top-bar">
        {/* Search now also queries your location text! */}
        <input 
          type="text" 
          placeholder="🔍 Search Reg, Date, or Location (e.g. VIE)" 
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
        <button onClick={() => setShowForm(!showForm)} className={`btn ${showForm ? 'btn-danger' : 'btn-secondary'}`}>
          {showForm ? 'Cancel Upload' : '📸 Add New Photo'}
        </button>
      </div>

      {showForm && (
        <div className="upload-card">
          <h2 style={{ marginTop: 0 }}>Upload New Photo</h2>
          <form onSubmit={handleUpload} className="upload-form">
            <input type="file" name="file" required accept="image/*" className="form-input" style={{backgroundColor: 'transparent', paddingLeft: 0}} />
            <input type="text" name="aircraft_type" placeholder="Type (e.g. A350-900)" required className="form-input" />
            <input type="text" name="registration" placeholder="Registration (e.g. D-AIXP)" required className="form-input" />
            <input type="text" name="serial_number" placeholder="Serial Number (e.g. MSN 123)" required className="form-input" />
            <input type="text" name="airline" placeholder="Airline (e.g. Lufthansa)" required className="form-input" />
            <input type="text" name="operator" placeholder="Operator (e.g. Lufthansa)" className="form-input" />
            {/* UPDATED: Placeholder encourages your new format */}
            <input type="text" name="airport" placeholder="Airport (e.g. Vienna International (VIE/LOWW))" className="form-input" />
            <input type="text" name="country" placeholder="Country (e.g. Germany)" className="form-input" />
            <input type="text" name="departure_airport" placeholder="Departure Airport (e.g. FRA)" className="form-input" />
            <input type="text" name="arrival_airport" placeholder="Arrival Airport (e.g. JFK)" className="form-input" />
            <input type="text" name="flight_number" placeholder="Flight Number (e.g. LH123)" className="form-input" />
            <button type="submit" disabled={isUploading} className="btn btn-primary">
              {isUploading ? 'Uploading...' : 'Upload'}
            </button>
          </form>
        </div>
      )}

      {/* UPDATED: Added a 3rd button for the Location grouping */}
      <div className="tab-container">
        <button 
          onClick={() => setGroupBy('airline')} 
          className={`tab ${groupBy === 'airline' ? 'active' : ''}`}
        >
          Sort by Airline
        </button>
        <button 
          onClick={() => setGroupBy('aircraft_type')} 
          className={`tab ${groupBy === 'aircraft_type' ? 'active' : ''}`}
        >
          Sort by Aircraft Type
        </button>
        <button 
          onClick={() => setGroupBy('location')} 
          className={`tab ${groupBy === 'location' ? 'active' : ''}`}
        >
          Sort by Location
        </button>
      </div>

      {Object.keys(groupedData).length === 0 ? (
        <p className="text-muted" style={{ textAlign: 'center', fontSize: '18px' }}>No photos found matching your search.</p>
      ) : (
        Object.entries(groupedData).map(([categoryName, registrations]) => (
          <div key={categoryName} style={{ marginBottom: '40px' }}>
            <h2 className="section-title">{categoryName}</h2>
            
            <div className="photo-grid">
              {Object.entries(registrations).map(([regName, regPhotos]) => (
                <div 
                  key={regName} 
                  onClick={() => setSelectedRegPhotos(regPhotos)} 
                  className="photo-card"
                >
                  <img 
                    src={`http://127.0.0.1:8000/${regPhotos[0].thumbnail_path}`} 
                    alt={regName} 
                    className="photo-img"
                  />
                  <div className="photo-card-info">
                    <h3 className="photo-title">
                      {getCountryFlag(regName)} {regName}
                    </h3>
                    <span className="badge">
                      {regPhotos.length} Photo{regPhotos.length > 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}

export default App