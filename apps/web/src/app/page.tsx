import { PublicHome } from "../components/public-home";
import CommandCenter from "../components/prototype-command-center";

export const dynamic = "force-dynamic";
export default function Home() {
  if (process.env.APP_MODE === "pilot") return <PublicHome />;
  return <CommandCenter />;
}
