import styles from "./Section.module.css";

export function Section({ title, sub }: { title: string; sub: string }) {
  return (
    <div className={styles.section}>
      <div className={styles.h}>{title}</div>
      <div className={styles.sub}>{sub}</div>
    </div>
  );
}
