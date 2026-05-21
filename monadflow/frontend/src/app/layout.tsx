export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body style={{ margin: 0, fontFamily: 'Inter, sans-serif', background: '#0b0f1a', color: '#e6edf3' }}>
        {children}
      </body>
    </html>
  );
}
