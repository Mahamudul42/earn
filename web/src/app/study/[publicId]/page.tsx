import { StudyClient } from "@/components/study/StudyClient";

// Participant ids are created at runtime, so there is nothing to prerender.
// One shell is emitted and Django serves it for every /study/<public_id>.
export function generateStaticParams() {
  return [{ publicId: "_" }];
}

export default function StudyPage() {
  return <StudyClient />;
}
