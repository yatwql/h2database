// Package widget renders table rows.
package widget

import (
	"fmt"
	"strings"
)

type Widget struct {
	Name string
}

type hidden struct{}

func (w *Widget) Render() string { return fmt.Sprint(w.Name) }
func reset(w *Widget)            { w.Name = strings.TrimSpace(w.Name) }
