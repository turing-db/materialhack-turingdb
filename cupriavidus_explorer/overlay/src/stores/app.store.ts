import { create } from 'zustand'

export type PageType = 'viewer' | 'help'
export type ThemeType = 'dark' | 'light'

export type AppStore = {
  theme: ThemeType
  setTheme: (v: ThemeType) => void

  page: PageType
  setPage: (v: PageType) => void

  graphName: string | undefined
  setGraphName: (v: string | undefined) => void
}

export const useAppStore = create<AppStore>((set) => ({
  theme: 'dark' as ThemeType,
  setTheme: (v: ThemeType) => set({ theme: v }),

  page: 'viewer' as PageType,
  setPage: (v: PageType) => set({ page: v }),

  // Default to the Cupriavidus necator graph so the explorer opens straight
  // into it (the graph must be loaded server-side — see viz/run.sh).
  graphName: 'cupriavidus_necator',
  setGraphName: (v: string | undefined) => set({ graphName: v }),
}))

export default useAppStore
