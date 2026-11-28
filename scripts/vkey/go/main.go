// Read signed-note verifier keys (c2sp.org/signed-note, "Verifier keys"), one per line, and print one JSON
// line for each: the parts of the key, or why it is refused. Standard library only.
//
//	<key name>+hex(32-bit key ID)+base64(signature type || public key)
//
// The name has no '+' and the key ID is hex, so the first two '+' are the only separators: the base64 part
// is standard base64 and may contain '+' itself.
package main

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"regexp"
	"strings"
)

// The public key length the C2SP texts fix for a signature type (signed-note, tlog-checkpoint).
var keyBytes = map[byte]int{0x01: 32, 0x04: 32, 0x06: 1312}

// Unicode White_Space: key names must not contain any of these.
var spaces = map[rune]bool{0x09: true, 0x0A: true, 0x0B: true, 0x0C: true, 0x0D: true, 0x20: true, 0x85: true, 0xA0: true, 0x1680: true, 0x2028: true, 0x2029: true, 0x202F: true, 0x205F: true, 0x3000: true}

func hasSpace(text string) bool {
	for _, r := range text {
		if spaces[r] || (r >= 0x2000 && r <= 0x200A) {
			return true
		}
	}
	return false
}

var hexID = regexp.MustCompile(`^[0-9a-fA-F]{8}$`)

func parse(vkey string) map[string]any {
	parts := strings.SplitN(vkey, "+", 3)
	if len(parts) != 3 {
		return map[string]any{"refused": "not-three-parts"}
	}
	name, id, b64 := parts[0], parts[1], parts[2]
	if name == "" || hasSpace(name) {
		return map[string]any{"refused": "bad-name"}
	}
	if !hexID.MatchString(id) {
		return map[string]any{"refused": "bad-key-id"}
	}
	raw, err := base64.StdEncoding.DecodeString(b64)
	if err != nil || len(raw) < 2 || base64.StdEncoding.EncodeToString(raw) != b64 {
		return map[string]any{"refused": "bad-base64"}
	}
	kind, key := raw[0], raw[1:]
	if n, known := keyBytes[kind]; known && len(key) != n {
		return map[string]any{"refused": "bad-key-length"}
	}
	h := sha256.New()
	h.Write([]byte(name))
	h.Write([]byte{'\n', kind})
	h.Write(key)
	keyID := hex.EncodeToString(h.Sum(nil)[:4])
	if keyID != strings.ToLower(id) {
		return map[string]any{"refused": "key-id-mismatch"}
	}
	sum := sha256.Sum256(key)
	return map[string]any{"name": name, "keyId": keyID, "type": fmt.Sprintf("0x%02x", kind),
		"keyBytes": len(key), "keySha256": hex.EncodeToString(sum[:])}
}

func main() {
	input, err := io.ReadAll(os.Stdin)
	if err != nil {
		panic(err)
	}
	for _, line := range strings.Split(string(input), "\n") {
		if line == "" {
			continue
		}
		out, _ := json.Marshal(parse(line))
		fmt.Println(string(out))
	}
}
