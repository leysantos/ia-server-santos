import { lazy, Suspense } from 'react';
import { Navbar } from './components/Navbar';
import { Footer } from './components/Footer';
import { Hero } from './sections/Hero';

const Features = lazy(() => import('./sections/Features').then((m) => ({ default: m.Features })));
const HowItWorks = lazy(() => import('./sections/HowItWorks').then((m) => ({ default: m.HowItWorks })));
const Benefits = lazy(() => import('./sections/Benefits').then((m) => ({ default: m.Benefits })));
const Demo = lazy(() => import('./sections/Demo').then((m) => ({ default: m.Demo })));
const Testimonials = lazy(() => import('./sections/Testimonials').then((m) => ({ default: m.Testimonials })));
const FAQ = lazy(() => import('./sections/FAQ').then((m) => ({ default: m.FAQ })));
const CTA = lazy(() => import('./sections/CTA').then((m) => ({ default: m.CTA })));

function SectionLoader() {
  return <div className="py-24" />;
}

export default function App() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <Suspense fallback={<SectionLoader />}>
          <Features />
          <HowItWorks />
          <Benefits />
          <Demo />
          <Testimonials />
          <FAQ />
          <CTA />
        </Suspense>
      </main>
      <Footer />
    </>
  );
}
