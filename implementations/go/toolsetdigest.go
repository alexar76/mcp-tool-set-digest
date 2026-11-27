// Reference implementation of mcp-tool-set-digest/1 (SPEC.md). Go 1.21+, standard library only.
//
//	go run . < tools.json                               prints both digests
//	go run . --vectors ../../vectors/vectors.json       checks every published vector
//
// Licence: Apache-2.0 OR MIT.
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"os"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
	"unicode/utf8"
)

// DigestError is a tool set the specification gives no digest (SPEC.md section 9).
type DigestError struct{ Code, Detail string }

func (e *DigestError) Error() string { return e.Code + ": " + e.Detail }

// --- parsing (section 3) -------------------------------------------------------------------------

// Parse reads JSON text into nil, bool, json.Number, string, []any and map[string]any.
//
// It is a reader of its own because encoding/json replaces an unpaired \uD800-\uDFFF escape with
// U+FFFD without saying so, which would give a digest to a string the specification gives none.
// Here such a surrogate is kept, in the three-byte form UTF-8 would give that code point; no valid
// UTF-8 string contains those bytes, so Canonical finds it. A number keeps its literal and is
// rounded to a double when it is written. In an object the last of two equal names wins.
func Parse(text []byte) (any, error) {
	if !utf8.Valid(text) {
		return nil, &DigestError{"TSD-TEXT", "the input is not valid UTF-8"}
	}
	r := &reader{text: text}
	value, err := r.value(1)
	if err != nil {
		return nil, err
	}
	r.space()
	if r.at < len(r.text) {
		return nil, r.fail("text after the JSON value")
	}
	return value, nil
}

// MaxLevel is the deepest level a reader must accept (section 12): the tools array is level 1, a
// tool level 2, an array or object held by a member of a tool level 3.
const MaxLevel = 512

// wrapperLevels: a JSON-RPC response and its result can wrap the tools array. The reader builds no
// array or object deeper than MaxLevel+wrapperLevels: nothing that deep can reach a digest (a digest
// that would cover it gives TSD-DEPTH), so such a container is read as an empty one of the same kind,
// which keeps its level and every answer.
const wrapperLevels = 2

type reader struct {
	text []byte
	at   int
}

func (r *reader) fail(what string) error { return fmt.Errorf("not JSON at byte %d: %s", r.at, what) }

func (r *reader) space() {
	for r.at < len(r.text) && strings.IndexByte(" \t\r\n", r.text[r.at]) >= 0 {
		r.at++
	}
}

// skip passes over the array or object that starts at r.at without building it, checking only
// that its brackets match; strings are passed over whole, so brackets inside them do not count.
func (r *reader) skip() error {
	var closers []byte
	for r.at < len(r.text) {
		switch c := r.text[r.at]; c {
		case '"':
			if _, err := r.str(); err != nil {
				return err
			}
			continue
		case '[':
			closers = append(closers, ']')
		case '{':
			closers = append(closers, '}')
		case ']', '}':
			if len(closers) == 0 || closers[len(closers)-1] != c {
				return r.fail("brackets do not match")
			}
			closers = closers[:len(closers)-1]
			if len(closers) == 0 {
				r.at++
				return nil
			}
		}
		r.at++
	}
	return r.fail("a nested value is not closed")
}

// value reads one JSON value; level is the level an array or object read here has (the outermost
// value is 1).
func (r *reader) value(level int) (any, error) {
	r.space()
	if r.at >= len(r.text) {
		return nil, r.fail("the text ends early")
	}
	if c := r.text[r.at]; (c == '[' || c == '{') && level > MaxLevel+wrapperLevels {
		if err := r.skip(); err != nil {
			return nil, err
		}
		if c == '[' {
			return []any{}, nil
		}
		return map[string]any{}, nil
	}
	switch c := r.text[r.at]; {
	case c == '{':
		r.at++
		object := map[string]any{}
		for first := true; ; first = false {
			r.space()
			if r.at < len(r.text) && r.text[r.at] == '}' && first {
				r.at++
				return object, nil
			}
			if r.at >= len(r.text) || r.text[r.at] != '"' {
				return nil, r.fail("a member name is expected")
			}
			name, err := r.str()
			if err != nil {
				return nil, err
			}
			r.space()
			if r.at >= len(r.text) || r.text[r.at] != ':' {
				return nil, r.fail("a colon is expected")
			}
			r.at++
			member, err := r.value(level + 1)
			if err != nil {
				return nil, err
			}
			object[name] = member
			r.space()
			if r.at < len(r.text) && r.text[r.at] == ',' {
				r.at++
				continue
			}
			if r.at < len(r.text) && r.text[r.at] == '}' {
				r.at++
				return object, nil
			}
			return nil, r.fail("a comma or } is expected")
		}
	case c == '[':
		r.at++
		array := []any{}
		for first := true; ; first = false {
			r.space()
			if r.at < len(r.text) && r.text[r.at] == ']' && first {
				r.at++
				return array, nil
			}
			item, err := r.value(level + 1)
			if err != nil {
				return nil, err
			}
			array = append(array, item)
			r.space()
			if r.at < len(r.text) && r.text[r.at] == ',' {
				r.at++
				continue
			}
			if r.at < len(r.text) && r.text[r.at] == ']' {
				r.at++
				return array, nil
			}
			return nil, r.fail("a comma or ] is expected")
		}
	case c == '"':
		return r.str()
	case c == '-' || (c >= '0' && c <= '9'):
		from := r.at
		for r.at < len(r.text) && strings.IndexByte("+-0123456789.eE", r.text[r.at]) >= 0 {
			r.at++
		}
		literal := string(r.text[from:r.at])
		if !json.Valid([]byte(literal)) {
			return nil, r.fail("not a number")
		}
		return json.Number(literal), nil
	}
	for word, value := range map[string]any{"true": true, "false": false, "null": nil} {
		if bytes.HasPrefix(r.text[r.at:], []byte(word)) {
			r.at += len(word)
			return value, nil
		}
	}
	return nil, r.fail("a value is expected")
}

func (r *reader) unit() (uint16, bool) {
	if r.at+4 > len(r.text) {
		return 0, false
	}
	value, err := strconv.ParseUint(string(r.text[r.at:r.at+4]), 16, 16)
	if err != nil {
		return 0, false
	}
	r.at += 4
	return uint16(value), true
}

func (r *reader) str() (string, error) {
	r.at++ // the opening quote
	var out []byte
	for r.at < len(r.text) {
		c := r.text[r.at]
		r.at++
		switch {
		case c == '"':
			return string(out), nil
		case c < 0x20:
			return "", r.fail("a control character inside a string")
		case c != '\\':
			out = append(out, c)
			continue
		}
		if r.at >= len(r.text) {
			break
		}
		escape := r.text[r.at]
		r.at++
		if at := strings.IndexByte(`"\/bfnrt`, escape); at >= 0 {
			out = append(out, "\"\\/\b\f\n\r\t"[at])
			continue
		}
		if escape != 'u' {
			return "", r.fail("an unknown escape")
		}
		unit, ok := r.unit()
		if !ok {
			return "", r.fail("a \\u escape needs four hex digits")
		}
		if unit >= 0xD800 && unit <= 0xDBFF && bytes.HasPrefix(r.text[r.at:], []byte(`\u`)) {
			saved := r.at
			r.at += 2
			if low, ok := r.unit(); ok && low >= 0xDC00 && low <= 0xDFFF {
				out = utf8.AppendRune(out, utf16.DecodeRune(rune(unit), rune(low)))
				continue
			}
			r.at = saved
		}
		if unit >= 0xD800 && unit <= 0xDFFF {
			// A surrogate on its own: kept as the bytes UTF-8 would give it, which are not valid UTF-8.
			out = append(out, 0xE0|byte(unit>>12), 0x80|byte(unit>>6)&0x3F, 0x80|byte(unit)&0x3F)
			continue
		}
		out = utf8.AppendRune(out, rune(unit))
	}
	return "", r.fail("a string does not end")
}

// --- canonical form (section 6): RFC 8785 --------------------------------------------------------

func utf16Less(a, b string) bool {
	x, y := utf16.Encode([]rune(a)), utf16.Encode([]rune(b))
	for i := 0; i < len(x) && i < len(y); i++ {
		if x[i] != y[i] {
			return x[i] < y[i]
		}
	}
	return len(x) < len(y)
}

// esNumber writes a double the way ECMAScript Number::toString does (RFC 8785 section 3.2.2.3).
func esNumber(f float64) string {
	if f == 0 {
		return "0" // -0 too
	}
	sign := ""
	if f < 0 {
		sign, f = "-", -f
	}
	// Shortest digits that round-trip, as d.ddde±xx.
	mantissa, exponent, _ := strings.Cut(strconv.FormatFloat(f, 'e', -1, 64), "e")
	s := strings.Replace(mantissa, ".", "", 1)
	exp10, _ := strconv.Atoi(exponent)
	k, n := len(s), exp10+1 // value = 0.s x 10^n
	switch {
	case k <= n && n <= 21:
		return sign + s + strings.Repeat("0", n-k)
	case 0 < n && n <= 21:
		return sign + s[:n] + "." + s[n:]
	case -6 < n && n <= 0:
		return sign + "0." + strings.Repeat("0", -n) + s
	}
	e := n - 1
	if k > 1 {
		s = s[:1] + "." + s[1:]
	}
	if e >= 0 {
		return sign + s + "e+" + strconv.Itoa(e)
	}
	return sign + s + "e-" + strconv.Itoa(-e)
}

func writeString(out *strings.Builder, text string) error {
	if !utf8.ValidString(text) {
		return &DigestError{"TSD-TEXT", "a string holds a lone surrogate"}
	}
	out.WriteByte('"')
	for _, r := range text {
		switch r {
		case '"':
			out.WriteString(`\"`)
		case '\\':
			out.WriteString(`\\`)
		case '\b':
			out.WriteString(`\b`)
		case '\f':
			out.WriteString(`\f`)
		case '\n':
			out.WriteString(`\n`)
		case '\r':
			out.WriteString(`\r`)
		case '\t':
			out.WriteString(`\t`)
		default:
			if r < 0x20 {
				fmt.Fprintf(out, `\u%04x`, r)
			} else {
				out.WriteRune(r)
			}
		}
	}
	out.WriteByte('"')
	return nil
}

func write(out *strings.Builder, value any) error {
	switch v := value.(type) {
	case nil:
		out.WriteString("null")
	case bool:
		out.WriteString(strconv.FormatBool(v))
	case json.Number:
		f, err := strconv.ParseFloat(string(v), 64) // nearest double, ties to even
		if err != nil || math.IsInf(f, 0) || math.IsNaN(f) {
			return &DigestError{"TSD-NUMBER", string(v) + " has no IEEE 754 double"}
		}
		out.WriteString(esNumber(f))
	case string:
		return writeString(out, v)
	case []any:
		out.WriteByte('[')
		for i, item := range v {
			if i > 0 {
				out.WriteByte(',')
			}
			if err := write(out, item); err != nil {
				return err
			}
		}
		out.WriteByte(']')
	case map[string]any:
		keys := make([]string, 0, len(v))
		for key := range v {
			keys = append(keys, key)
		}
		sort.Slice(keys, func(i, j int) bool { return utf16Less(keys[i], keys[j]) })
		out.WriteByte('{')
		for i, key := range keys {
			if i > 0 {
				out.WriteByte(',')
			}
			if err := writeString(out, key); err != nil {
				return err
			}
			out.WriteByte(':')
			if err := write(out, v[key]); err != nil {
				return err
			}
		}
		out.WriteByte('}')
	default:
		return fmt.Errorf("%T is not a JSON value", value)
	}
	return nil
}

// Canonical is the RFC 8785 text of a value.
func Canonical(value any) (string, error) {
	var out strings.Builder
	err := write(&out, value)
	return out.String(), err
}

// --- the two digests (sections 4 to 8) -------------------------------------------------------------

func toolObject(tool any) (map[string]any, error) {
	object, ok := tool.(map[string]any)
	if !ok {
		return nil, &DigestError{"TSD-TOOL", "a tool entry is not a JSON object"}
	}
	if name, ok := object["name"].(string); !ok || name == "" {
		return nil, &DigestError{"TSD-TOOL", "a tool entry has no non-empty string name"}
	}
	return object, nil
}

func contractEntry(tool any) (map[string]any, error) {
	t, err := toolObject(tool)
	if err != nil {
		return nil, err
	}
	entry := map[string]any{"name": t["name"], "description": "", "inputSchema": map[string]any{}}
	if description, ok := t["description"].(string); ok {
		entry["description"] = description
	}
	if schema, ok := t["inputSchema"].(map[string]any); ok {
		entry["inputSchema"] = schema
	}
	if schema, ok := t["outputSchema"].(map[string]any); ok {
		entry["outputSchema"] = schema
	}
	return entry, nil
}

// Digest is one digest with the canonical text it is the hash of.
type Digest struct{ Digest, Canonical string }

// digestOf orders the entries (by name in UTF-16 code units, entries sharing a name by their
// canonical UTF-8 bytes) and hashes the canonical text of the array.
func digestOf(entries []map[string]any) (Digest, error) {
	texts := make([]string, len(entries))
	for i, entry := range entries {
		text, err := Canonical(entry)
		if err != nil {
			return Digest{}, err
		}
		texts[i] = text
	}
	order := make([]int, len(entries))
	for i := range order {
		order[i] = i
	}
	sort.SliceStable(order, func(i, j int) bool {
		a, b := entries[order[i]]["name"].(string), entries[order[j]]["name"].(string)
		if a != b {
			return utf16Less(a, b)
		}
		return texts[order[i]] < texts[order[j]] // Go compares strings as unsigned bytes
	})
	parts := make([]string, len(order))
	for i, index := range order {
		parts[i] = texts[index]
	}
	text := "[" + strings.Join(parts, ",") + "]"
	sum := sha256.Sum256([]byte(text))
	return Digest{"sha256-" + base64.StdEncoding.EncodeToString(sum[:]), text}, nil
}

// ToolsOf extracts a complete tools array or the tools from an unpaginated tools/list result.
func ToolsOf(value any) ([]any, error) {
	if tools, ok := value.([]any); ok {
		return tools, nil
	}
	if object, ok := value.(map[string]any); ok {
		wrapped, _ := object["result"].(map[string]any)
		for _, result := range []map[string]any{object, wrapped} {
			_, hasTools := result["tools"]
			_, hasResult := result["result"]
			if hasTools && hasResult {
				return nil, &DigestError{"TSD-TOOL", "an object holds both tools and result (section 3)"}
			}
			if tools, ok := result["tools"].([]any); ok {
				if _, hasCursor := result["nextCursor"]; hasCursor {
					return nil, &DigestError{"TSD-PAGE", "collect all pages and pass the joined tools array"}
				}
				return tools, nil
			}
		}
	}
	return nil, &DigestError{"TSD-TOOL", "the input holds no tools array"}
}

// deeperThan reports whether an array or object inside value (itself at level) sits deeper than
// MaxLevel. It walks with an explicit stack.
func deeperThan(value any, level int) bool {
	type item struct {
		value any
		level int
	}
	stack := []item{{value, level}}
	for len(stack) > 0 {
		top := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		if top.level > MaxLevel {
			return true
		}
		switch v := top.value.(type) {
		case map[string]any:
			for _, child := range v {
				switch child.(type) {
				case map[string]any, []any:
					stack = append(stack, item{child, top.level + 1})
				}
			}
		case []any:
			for _, child := range v {
				switch child.(type) {
				case map[string]any, []any:
					stack = append(stack, item{child, top.level + 1})
				}
			}
		}
	}
	return false
}

// checkDepth applies section 12 to a tool's contract entry or its extras, read at level 2 (the
// tool's own level), so the values of its members are at level 3.
func checkDepth(name string, projection map[string]any) error {
	if deeperThan(projection, 2) {
		return &DigestError{"TSD-DEPTH", "a value of tool " + strconv.Quote(name) + " is nested deeper than level " + strconv.Itoa(MaxLevel)}
	}
	return nil
}

// Contract is the contract digest of a tools array.
func Contract(tools []any) (Digest, error) {
	entries := make([]map[string]any, len(tools))
	for i, tool := range tools {
		entry, err := contractEntry(tool)
		if err != nil {
			return Digest{}, err
		}
		entries[i] = entry
	}
	for _, entry := range entries {
		if err := checkDepth(entry["name"].(string), entry); err != nil {
			return Digest{}, err
		}
	}
	return digestOf(entries)
}

var contractMembers = map[string]bool{"name": true, "description": true, "inputSchema": true, "outputSchema": true}

// ExtrasObject is {"tools": {name: extras}} for the tools that carry a member outside the contract,
// or nil when none does (section 8).
func ExtrasObject(tools []any) (map[string]any, error) {
	byName := map[string]any{}
	for _, item := range tools {
		tool, err := toolObject(item)
		if err != nil {
			return nil, err
		}
		extra := map[string]any{}
		for key, value := range tool {
			if !contractMembers[key] {
				extra[key] = value
			}
		}
		if len(extra) == 0 {
			continue
		}
		name := tool["name"].(string)
		if _, twice := byName[name]; twice {
			return nil, &DigestError{"TSD-NAME", "two tools named " + strconv.Quote(name) + " both carry extras"}
		}
		byName[name] = extra
	}
	if len(byName) == 0 {
		return nil, nil
	}
	return map[string]any{"tools": byName}, nil
}

// Extras is the extras digest of a tools array. ok is false when no tool carries extras: the set
// then has no extras digest, which is a state and not an error.
func Extras(tools []any) (digest Digest, ok bool, err error) {
	body, err := ExtrasObject(tools)
	if err != nil || body == nil {
		return Digest{}, false, err
	}
	names := make([]string, 0, len(body["tools"].(map[string]any)))
	for name := range body["tools"].(map[string]any) {
		names = append(names, name)
	}
	sort.Strings(names) // the same tool is named whatever order the map iterates in
	for _, name := range names {
		if err := checkDepth(name, body["tools"].(map[string]any)[name].(map[string]any)); err != nil {
			return Digest{}, false, err
		}
	}
	text, err := Canonical(body)
	if err != nil {
		return Digest{}, false, err
	}
	sum := sha256.Sum256([]byte(text))
	return Digest{"sha256-" + base64.StdEncoding.EncodeToString(sum[:]), text}, true, nil
}

// HexForm is the same hash as sha256:<lowercase hex>.
func HexForm(digest string) string {
	raw, _ := base64.StdEncoding.DecodeString(strings.SplitN(digest, "-", 2)[1])
	return "sha256:" + hex.EncodeToString(raw)
}

// Result is one digest of a set, the code of the reason it cannot be computed, or (for the extras
// digest) None: no tool carries extras.
type Result struct {
	Digest    string
	Canonical string
	Error     string
	None      bool
}

func result(d Digest, err error) Result {
	if err == nil {
		return Result{Digest: d.Digest, Canonical: d.Canonical}
	}
	if digestError, ok := err.(*DigestError); ok {
		return Result{Error: digestError.Code}
	}
	return Result{Error: "TSD-JSON"}
}

// Both computes the two digests of JSON text apart, so a member only the extras digest covers
// cannot take the contract digest away. The error covers parse failures and incomplete inputs.
func Both(text []byte) (contract, extras Result, err error) {
	value, err := Parse(text)
	if err != nil {
		return
	}
	tools, err := ToolsOf(value)
	if err != nil {
		return
	}
	digest, ok, extrasErr := Extras(tools)
	extras = result(digest, extrasErr)
	extras.None = extrasErr == nil && !ok
	return result(Contract(tools)), extras, nil
}

// --- command line ---------------------------------------------------------------------------------

type expected struct {
	Digest    *string `json:"digest"` // null in the file: no tool carries extras
	Hex       string  `json:"hex"`
	Canonical string  `json:"canonical"`
	Error     string  `json:"error"`
}

func (e expected) digest() string {
	if e.Digest == nil {
		return ""
	}
	return *e.Digest
}

type vector struct {
	ID       string   `json:"id"`
	Tools    string   `json:"tools"`
	Contract expected `json:"contract"`
	Extras   expected `json:"extras"`
}

type relation struct {
	IDs    []string `json:"ids"`
	Digest string   `json:"digest"`
}

func checkVectors(path string) int {
	raw, err := os.ReadFile(path)
	if err != nil {
		fmt.Println(err)
		return 1
	}
	var document struct {
		Vectors []vector   `json:"vectors"`
		Equal   []relation `json:"equal"`
		Differ  []relation `json:"differ"`
	}
	if err := json.Unmarshal(raw, &document); err != nil {
		fmt.Println(err)
		return 1
	}
	failed := 0
	byID := map[string]map[string]string{}
	for _, v := range document.Vectors {
		contract, extras, err := Both([]byte(v.Tools))
		if err != nil {
			contract, extras = result(Digest{}, err), result(Digest{}, err)
		}
		byID[v.ID] = map[string]string{"contract": contract.Digest, "extras": extras.Digest}
		for _, pair := range []struct {
			kind string
			got  Result
			want expected
		}{{"contract", contract, v.Contract}, {"extras", extras, v.Extras}} {
			wantNone := pair.want.Error == "" && pair.want.Digest == nil
			if pair.got.Digest != pair.want.digest() || pair.got.Canonical != pair.want.Canonical || pair.got.Error != pair.want.Error || pair.got.None != wantNone {
				failed++
				fmt.Printf("FAIL %s %s: %s%s != %s%s\n", v.ID, pair.kind, pair.got.Digest, pair.got.Error, pair.want.digest(), pair.want.Error)
			} else if pair.want.digest() != "" && HexForm(pair.want.digest()) != pair.want.Hex {
				failed++
				fmt.Printf("FAIL %s %s: hex form\n", v.ID, pair.kind)
			}
		}
	}
	for _, rows := range []struct {
		name string
		rows []relation
		same bool
	}{{"equal", document.Equal, true}, {"differ", document.Differ, false}} {
		for _, row := range rows.rows {
			first, second := byID[row.IDs[0]][row.Digest], byID[row.IDs[1]][row.Digest]
			if first == "" || second == "" || (first == second) != rows.same {
				failed++
				fmt.Printf("FAIL %s %v %s\n", rows.name, row.IDs, row.Digest)
			}
		}
	}
	fmt.Printf("go: %d vectors, %d failed\n", len(document.Vectors), failed)
	if failed > 0 {
		return 1
	}
	return 0
}

func main() {
	if len(os.Args) == 3 && os.Args[1] == "--vectors" {
		os.Exit(checkVectors(os.Args[2]))
	}
	if len(os.Args) == 2 && os.Args[1] == "--canonical" {
		// RFC 8785 alone, for any JSON value (vectors/jcs-subset.json): the canonical text and its SHA-256.
		text, _ := io.ReadAll(os.Stdin)
		value, err := Parse(text)
		var canon string
		if err == nil {
			canon, err = Canonical(value)
		}
		if err != nil {
			out, _ := json.Marshal(map[string]string{"error": result(Digest{}, err).Error})
			fmt.Println(string(out))
			os.Exit(2)
		}
		sum := sha256.Sum256([]byte(canon))
		out, _ := json.Marshal(map[string]string{"canonical": canon, "sha256": hex.EncodeToString(sum[:])})
		fmt.Println(string(out))
		os.Exit(0)
	}
	text, _ := io.ReadAll(os.Stdin)
	contract, extras, err := Both(text)
	if err != nil {
		out, _ := json.Marshal(map[string]string{"error": result(Digest{}, err).Error, "detail": err.Error()})
		fmt.Println(string(out))
		os.Exit(2)
	}
	show := func(r Result) any {
		switch {
		case r.Error != "":
			return map[string]string{"error": r.Error}
		case r.None:
			return nil
		}
		return r.Digest
	}
	out, _ := json.Marshal(map[string]any{"contract": show(contract), "extras": show(extras)})
	fmt.Println(string(out))
	if contract.Error != "" || extras.Error != "" {
		os.Exit(2)
	}
}
