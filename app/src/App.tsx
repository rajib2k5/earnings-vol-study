import { AboutPage } from './lib/about'
import { ArchitecturePage } from './lib/ArchitecturePage'
import { FunnelPage } from './lib/FunnelPage'
import { IvMeasuresPage } from './lib/IvMeasuresPage'
import { MetaFooter } from './lib/MetaFooter'
import { AppShell, type ShellPage } from './lib/shell'
import { StudySections } from './lib/StudySections'
import { ABOUT_INTRO, PITCH, PROJECT_SLUG, PROJECT_TITLE } from './lib/studyContent'
import { ThreeDPreview } from './three/ThreeDPreview'

const PAGES: ShellPage[] = [
  {
    id: 'about',
    label: 'About',
    render: () => (
      <AboutPage slug={PROJECT_SLUG} content={{ intro: ABOUT_INTRO }}>
        <StudySections />
      </AboutPage>
    ),
  },
  { id: 'sample', label: 'Sample', render: () => <FunnelPage /> },
  { id: 'iv', label: 'IV measures', render: () => <IvMeasuresPage /> },
  { id: 'architecture', label: 'Architecture', render: () => <ArchitecturePage slug={PROJECT_SLUG} /> },
  { id: '3d', label: '3D preview', render: () => <ThreeDPreview /> },
]

export default function App() {
  return <AppShell slug={PROJECT_SLUG} title={PROJECT_TITLE} subtitle={PITCH} pages={PAGES} footer={<MetaFooter />} />
}
