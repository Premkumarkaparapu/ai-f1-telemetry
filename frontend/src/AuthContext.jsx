import { useAuth, useUser } from '@clerk/clerk-react'

// Drop-in replacement for the old AuthContext hook
// Maps Clerk's useUser/useAuth to the same shape as the old context
export function useAppAuth() {
  const { isSignedIn, isLoaded } = useAuth()
  const { user } = useUser()

  return {
    user: isSignedIn && user ? {
      id:               user.id,
      username:         user.username || user.firstName || user.emailAddresses[0]?.emailAddress?.split('@')[0],
      email:            user.primaryEmailAddress?.emailAddress,
      full_name:        user.fullName,
      avatar_initials:  user.firstName?.[0] + (user.lastName?.[0] || ''),
      avatar_color:     '#e8002d',
      // Clerk's imageUrl for profile photo
      imageUrl:         user.imageUrl,
    } : null,
    loading: !isLoaded,
    isSignedIn: !!isSignedIn,
  }
}
