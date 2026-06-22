import { createRoot } from "react-dom/client";
import { installStorageShim } from "./lib/storageShim";
import GraphingCalculator from "./GraphingCalculator";

// window.storage 주입을 render보다 *먼저* 실행한다.
// 컴포넌트의 useEffect가 mount 직후 저장소를 읽으므로(학습 기록·저장 그래프 목록 복원) 순서가 중요.
installStorageShim();

createRoot(document.getElementById("root")).render(<GraphingCalculator />);
