import { useState } from 'react'

function App() {
  const [residents, setResidents] = useState([])
  const [bills, setBills] = useState([])
  const [message, setMessage] = useState('')

  const loadResidents = async () => {
    try {
      setMessage('Loading residents...')

      const response = await fetch('/api/v1/residents', {
        credentials: 'include'
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      setResidents(Array.isArray(data) ? data : [])
      setMessage('Residents loaded from Flask successfully.')
    } catch (error) {
      console.error(error)
      setMessage(`Residents error: ${error.message}`)
    }
  }

  const loadBills = async () => {
    try {
      setMessage('Loading bills...')

      const response = await fetch('/api/v1/bills', {
        credentials: 'include'
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      setBills(Array.isArray(data) ? data : [])
      setMessage('Bills loaded from Flask successfully.')
    } catch (error) {
      console.error(error)
      setMessage(`Bills error: ${error.message}`)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Society Maintenance</h1>
        <p>React + Flask + MySQL</p>
      </header>

      <section className="connection">
        <h2>Backend Connection</h2>
        <p>
          React is connected to Flask through the Vite proxy.
        </p>

        <div className="buttons">
          <button onClick={loadResidents}>
            Load Residents
          </button>

          <button onClick={loadBills}>
            Load Bills
          </button>
        </div>

        {message && <p className="message">{message}</p>}
      </section>

      {residents.length > 0 && (
        <section>
          <h2>Residents</h2>

          <div className="cards">
            {residents.map((resident) => (
              <div className="card" key={resident.id}>
                <h3>{resident.full_name}</h3>
                <p>Mobile: {resident.mobile || '-'}</p>
                <p>Email: {resident.email || '-'}</p>
                <p>Type: {resident.resident_type || '-'}</p>
                <p>Status: {resident.occupancy_status || '-'}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {bills.length > 0 && (
        <section>
          <h2>Maintenance Bills</h2>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Bill No.</th>
                  <th>Month</th>
                  <th>Total</th>
                  <th>Paid</th>
                  <th>Remaining</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {bills.map((bill) => (
                  <tr key={bill.id}>
                    <td>{bill.bill_number}</td>
                    <td>{bill.billing_month}</td>
                    <td>₹{bill.total_amount}</td>
                    <td>₹{bill.amount_paid}</td>
                    <td>₹{bill.remaining_amount}</td>
                    <td>{bill.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}

export default App
