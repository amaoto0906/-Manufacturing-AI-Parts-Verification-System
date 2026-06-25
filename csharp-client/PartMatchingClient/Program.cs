using PartMatching;

// 既存 C# システムからの呼び出し例。
// 使い方: dotnet run -- <画像パス> <期待品番> [APIベースURL]
if (args.Length < 2)
{
    Console.WriteLine("使い方: dotnet run -- <画像パス> <期待品番> [APIベースURL]");
    Console.WriteLine("例:     dotnet run -- ./capture.png PRS-00001 http://127.0.0.1:8077");
    return 1;
}

string imagePath = args[0];
string expected = args[1];
string baseUrl = args.Length >= 3 ? args[2] : "http://127.0.0.1:8077";

using var client = new PartMatchingApiClient(baseUrl, TimeSpan.FromSeconds(10));

try
{
    var r = await client.InspectAsync(imagePath, expected, operatorId: "OP001", lineId: "LINE01");

    Console.WriteLine($"判定        : {r.Result}  (信頼度 {r.Confidence:P1}, マージン {r.Margin:F3}, {r.ProcessingTimeMs:F1}ms)");
    Console.WriteLine($"判定品番    : {r.PredictedPartNo}   期待品番: {r.ExpectedPartNo}");
    Console.WriteLine($"理由        : {r.Reason}");
    Console.WriteLine("上位候補    :");
    foreach (var c in r.TopCandidates.Take(3))
        Console.WriteLine($"  - {c.PartNo}  類似度 {c.Score:F4}  (Gr {c.GroupId?.ToString() ?? "-"})");

    // 戻り値に応じて設備を制御する（ここでは標準出力で代替）
    switch (PartMatchingApiClient.ToLineAction(r.Action))
    {
        case LineAction.Pass:
            Console.WriteLine("=> [PLC] 出荷OK。コンベア前進を許可。");
            break;
        case LineAction.Block:
            Console.WriteLine("=> [PLC] 出荷停止！ 取り違えの疑い。排出シュートへ振り分け、警報。");
            break;
        case LineAction.ManualCheck:
            Console.WriteLine("=> [HMI] 要確認。作業者へ目視確認を要求（Top候補を提示）。");
            break;
        case LineAction.Retake:
            Console.WriteLine("=> [CAM] 画質不良。再撮影を指示。");
            break;
    }
    return 0;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"エラー: {ex.Message}");
    // AIサーバ停止時の代替フロー（フェイルセーフ）: 自動OKは出さず、必ず要確認に倒す
    Console.WriteLine("=> [フェイルセーフ] AI照合不可のため、自動出荷は行わず作業者確認に切替。");
    return 2;
}
