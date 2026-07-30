export function PageHeader({ title, description }: { title: string; description: string }) {
  return (
    <header className="mb-5">
      <h1 className="text-xl font-bold tracking-tight text-ink sm:text-2xl">{title}</h1>
      <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">{description}</p>
    </header>
  );
}
