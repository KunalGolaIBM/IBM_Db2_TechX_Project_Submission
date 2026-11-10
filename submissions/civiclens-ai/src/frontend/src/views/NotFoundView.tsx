import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card, EmptyState } from '../components/ui'

export function NotFoundView() {
  return (
    <Card>
      <EmptyState
        icon={<Compass />}
        title="Page not found"
        action={
          <Link to="/" className="text-sm font-medium text-copper-400 hover:text-copper-300">
            Back to the overview
          </Link>
        }
      >
        That address does not match any CivicLens page.
      </EmptyState>
    </Card>
  )
}
