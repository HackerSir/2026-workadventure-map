// The optimizer silently skips a map that fails this schema, which would drop it from the build.
import fs from "fs";
import { ITiledMap } from "@workadventure/tiled-map-type-guard";

const result = ITiledMap.safeParse(JSON.parse(fs.readFileSync(process.argv[2] ?? "map.tmj", "utf8")));
if (result.success) {
  console.log(`${process.argv[2] ?? "map.tmj"} is valid`);
} else {
  console.error(result.error.issues.slice(0, 8).map(issue => `${issue.path.join(".")}: ${issue.message}`).join("\n"));
  process.exit(1);
}
