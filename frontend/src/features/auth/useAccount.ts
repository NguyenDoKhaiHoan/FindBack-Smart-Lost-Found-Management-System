import { useQuery } from '@tanstack/react-query'
import { identityApi } from '../../lib/api/system'
import { useSession } from './session'

export function useAccount() {
  const { token, actorId } = useSession()
  return useQuery({
    queryKey: ['account', 'profile', actorId],
    enabled: Boolean(token),
    queryFn: ({ signal }) => identityApi.me(signal),
  })
}
