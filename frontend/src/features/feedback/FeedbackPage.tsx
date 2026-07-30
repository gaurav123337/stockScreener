import { Section } from "@/components/Section";
import { FeedbackForm } from "./components/FeedbackForm";

export default function FeedbackPage() {
  return (
    <>
      <Section
        title="Share feedback"
        sub="Tell us what worked, what felt confusing, or what should improve. Format and highlight the exact parts you want us to notice."
      />
      <FeedbackForm />
    </>
  );
}
