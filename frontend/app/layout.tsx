import type { Metadata } from 'next';
import './styles.css';
export const metadata:Metadata={title:'CLIPRA AI NEXT',description:'Real video clipping and review with source-preserving exports'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}