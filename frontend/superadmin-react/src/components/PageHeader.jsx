export default function PageHeader({ title, subtitle }) {
  return (
    <div className="page-header">
      <h2 className="title">{title}</h2>
      {subtitle ? <p className="subtitle">{subtitle}</p> : null}
    </div>
  );
}
